<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { chartColorForTheme, MAX_TIME_SERIES_ITEMS, type ChartSeries } from '~/composables/useAnalytics'

use([CanvasRenderer, LineChart, BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent])
const props = withDefaults(defineProps<{ series: ChartSeries[], height?: number, pie?: boolean }>(), { height: 300, pie: false })
const emit = defineEmits<{ ready: [] }>()
const { isDark } = useDashboardTheme()

const option = computed(() => {
  const dark = isDark.value
  const color = dark ? '#9ca59b' : '#687365'
  const border = dark ? 'rgba(151, 166, 146, .12)' : 'rgba(43, 57, 42, .10)'
  const darkPieColors = ['#b4f273', '#79c8ee', '#c3a5ff', '#f5c978', '#ff8e84', '#65d6b4', '#9da8ff']
  const pieColors = dark ? darkPieColors : darkPieColors.map((value) => chartColorForTheme(value, false))
  const seriesColor = (item: ChartSeries) => chartColorForTheme(item.color, dark)
  const isPie = props.pie && props.series.length === 1
  const axisCount = isPie ? 0 : Math.max(1, ...props.series.map((item) => (item.yAxisIndex ?? 0) + 1))
  const extraRightAxes = Math.max(0, axisCount - 2)
  const axisColor = (index: number) => {
    const series = props.series.find((item) => (item.yAxisIndex ?? 0) === index)
    return series ? seriesColor(series) : color
  }
  const axisFormat = (index: number) => props.series.find((item) => (item.yAxisIndex ?? 0) === index)?.valueFormat
  const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>\"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', "'": '&#39;',
  })[character]!)
  const compactValue = (value: number) => {
    const magnitude = Math.abs(value)
    const options: Intl.NumberFormatOptions = magnitude >= 1_000
      ? { notation: 'compact', maximumFractionDigits: 2 }
      : { maximumFractionDigits: magnitude >= 1 ? 4 : 6 }
    return new Intl.NumberFormat('en-US', options).format(value)
  }
  return {
    animationDuration: 650,
    color: props.series.map((item) => seriesColor(item)),
    tooltip: {
      trigger: isPie ? 'item' : 'axis',
      backgroundColor: dark ? '#20251f' : '#ffffff',
      borderColor: border,
      textStyle: { color: dark ? '#f1f4ee' : '#20261f', fontFamily: 'DM Sans, sans-serif', fontSize: 12 },
      axisPointer: { type: 'line', lineStyle: { color: dark ? '#606b5e' : '#aeb6a9', type: 'dashed' } },
      formatter: (params: any) => {
        const points = Array.isArray(params) ? params : [params]
        const heading = points[0]?.axisValueLabel ?? points[0]?.name ?? ''
        const axisValue = points[0]?.axisValue ?? (Array.isArray(points[0]?.value) ? points[0].value[0] : points[0]?.name)
        const rows = (isPie
          ? points.map((point: any) => {
              const meta = props.series[point.seriesIndex]
              const raw = Array.isArray(point.value) ? point.value.at(-1) : point.value
              const amount = Number(raw)
              if (!Number.isFinite(amount)) return ''
              return { name: point.seriesName, marker: point.marker, display: meta?.valueFormat === 'percent'
                ? `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(amount)}%`
                : compactValue(amount) }
            })
          : props.series.map((meta, index) => {
              const point = points.find((item: any) => item.seriesIndex === index)
              const observation = (meta.data as [string, number | null][]).find(([date]) => String(date) === String(axisValue))
              const raw = observation?.[1] ?? null
              const amount = raw == null ? null : Number(raw)
              const display = amount == null || !Number.isFinite(amount)
                ? '—'
                : meta.valueFormat === 'percent'
                  ? `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(amount)}%`
                  : compactValue(amount)
              return {
                name: meta.name,
                marker: point?.marker ?? `<span style="color:${seriesColor(meta)}">●</span>`,
                display,
              }
            })
        ).map((row: any) => row ? `<div style="display:flex;align-items:center;gap:7px;margin-top:5px">${row.marker ?? ''}<span>${escapeHtml(row.name)}</span><strong style="margin-left:auto;font-variant-numeric:tabular-nums">${row.display}</strong></div>` : '').join('')
        return `<div style="min-width:150px"><div style="font-weight:600;margin-bottom:4px">${escapeHtml(heading)}</div>${rows}</div>`
      },
    },
    legend: isPie ? { show: true, bottom: 0, icon: 'circle', textStyle: { color, fontSize: 11 } } : { show: props.series.length > 1, top: 0, left: 12, right: 0, width: '100%', itemWidth: 8, itemHeight: 8, itemGap: 10, icon: 'circle', textStyle: { color, fontSize: 10 } },
    grid: isPie ? undefined : { left: 10, right: 14 + extraRightAxes * 40, top: props.series.length > 6 ? 52 : props.series.length > 1 ? 34 : 14, bottom: 8, containLabel: true },
    xAxis: isPie ? undefined : {
      type: 'category', boundaryGap: props.series.some((item) => item.type === 'bar'),
      axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color, fontSize: 10, hideOverlap: true, margin: 14 },
      splitLine: { show: false },
    },
    yAxis: isPie ? undefined : Array.from({ length: axisCount }, (_, index) => ({
      type: 'value',
      scale: true,
      position: index === 0 ? 'left' : 'right',
      offset: index > 1 ? (index - 1) * 40 : 0,
      name: axisFormat(index) === 'percent' ? 'Rate (%)' : undefined,
      nameLocation: 'end',
      nameTextStyle: { color: axisColor(index), fontSize: 9 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: axisColor(index), fontSize: 10, formatter: (value: number) => axisFormat(index) === 'percent' ? `${Intl.NumberFormat('en', { maximumFractionDigits: 1 }).format(value)}%` : Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value) },
      splitLine: index === 0 ? { lineStyle: { color: border, type: 'dashed' } } : { show: false },
    })),
    series: props.series.map((item) => ({
      name: item.name,
      type: item.type,
      data: item.type === 'pie'
        ? (item.data as { name: string, value: number }[]).map((slice, index) => ({ ...slice, itemStyle: { color: pieColors[index % pieColors.length] } }))
        : (item.data as [string, number | null][]).slice(-MAX_TIME_SERIES_ITEMS),
      yAxisIndex: item.yAxisIndex ?? 0,
      smooth: item.smooth ?? true,
      connectNulls: false,
      showSymbol: false,
      symbol: 'circle',
      symbolSize: 7,
      stack: item.stack,
      emphasis: { focus: 'series' },
      lineStyle: { width: 2.3 },
      itemStyle: {
        color: item.pointColors
          ? (params: { dataIndex: number }) => chartColorForTheme(item.pointColors?.[params.dataIndex] ?? item.color, dark)
          : seriesColor(item),
        borderRadius: item.type === 'bar' ? [4, 4, 0, 0] : 0,
      },
      areaStyle: item.area ? { opacity: dark ? 0.10 : 0.08 } : undefined,
      ...(item.type === 'pie' ? { radius: ['52%', '76%'], center: ['50%', '45%'], label: { color, formatter: '{b}' }, labelLine: { lineStyle: { color } } } : {}),
    })),
  }
})
</script>

<template>
  <VChart :option="option" :autoresize="true" class="echart-canvas" :style="{ height: `${height}px` }" @finished="emit('ready')" />
</template>
