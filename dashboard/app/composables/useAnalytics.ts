export type AnalyticsDocument = Record<string, any>

export function analyticsDataUrl(baseUrl: string, path: string) {
  const base = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl
  const relativePath = path.startsWith('/') ? path.slice(1) : path
  return `${base}/${relativePath}`
}

export function formatIdentifierLabel(value: string | null | undefined) {
  if (!value) return ''
  const normalized = value.trim()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
  return normalized.split(' ')
    .filter(Boolean)
    .map((word) => word === word.toLocaleLowerCase('en-US')
      ? word.charAt(0).toLocaleUpperCase('en-US') + word.slice(1)
      : word)
    .join(' ')
}

export async function fetchAnalytics<T extends AnalyticsDocument = AnalyticsDocument>(path: string, baseUrl: string) {
  return await $fetch<T>(analyticsDataUrl(baseUrl, path))
}

export async function fetchAnalyticsOrEmpty(path: string, baseUrl: string) {
  try {
    return await fetchAnalytics(path, baseUrl)
  }
  catch {
    return { schema_version: '1.0.0', data_status: 'unavailable' } as AnalyticsDocument
  }
}

export function formatCompact(
  value: number | string | null | undefined,
  maximumFractionDigits = 1,
  minimumFractionDigits = 0,
) {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return new Intl.NumberFormat('en-US', {
    notation: amount >= 100_000 ? 'compact' : 'standard',
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(amount)
}

export function formatCurrency(value: number | string | null | undefined, currency = 'USD', maximumFractionDigits = 2, minimumFractionDigits = 0) {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency, notation: amount >= 100_000 ? 'compact' : 'standard',
    minimumFractionDigits, maximumFractionDigits,
  }).format(amount)
}

export function formatPercent(value: number | string | null | undefined) {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return `${amount > 0 ? '+' : ''}${amount.toFixed(2)}%`
}

export function latest<T extends Record<string, any>>(rows: T[] | undefined, key: string) {
  return rows?.length ? rows[rows.length - 1]?.[key] : undefined
}

export type ChartPoint = [string, number | null]
export const MAX_TIME_SERIES_ITEMS = 365
const lightModeChartColors: Record<string, string> = {
  // Soft, low-saturation tones for white backgrounds. Dark theme keeps the
  // brighter source colors; light theme reduces both saturation and weight.
  '#b4f273': '#829873',
  '#79c8ee': '#7699a8',
  '#c3a5ff': '#9889ae',
  '#f5c978': '#938662',
  '#ff8e84': '#b7857f',
  '#65d6b4': '#70998b',
  '#9da8ff': '#818bae',
  '#f49abd': '#aa8194',
  '#a7b0a2': '#899187',
  '#ff9f6e': '#a27d6e',
}

export function chartColorForTheme(color: string | undefined, isDark: boolean) {
  const value = color ?? '#b4f273'
  return isDark ? value : lightModeChartColors[value.toLowerCase()] ?? value
}

export type ChartSeries = {
  name: string
  type: 'line' | 'bar' | 'pie'
  data: ChartPoint[] | { name: string, value: number }[]
  color?: string
  yAxisIndex?: number
  valueFormat?: 'percent'
  area?: boolean
  smooth?: boolean
  stack?: string
  pointColors?: string[]
}

type SeriesField = { key: string, label: string, type?: 'line' | 'bar', color?: string, axis?: number, area?: boolean, valueFormat?: 'percent' }

export function makeCurrencySeries(
  documents: Record<string, AnalyticsDocument>,
  fieldsByCurrency: Record<string, SeriesField[]>,
) {
  const result: Record<string, Record<string, ChartSeries[]>> = {}
  for (const [period, document] of Object.entries(documents)) {
    const rows = [...(document.observations ?? document.items ?? [])].sort((a, b) => {
      const dateA = String(a.period_start ?? a.date ?? a.period ?? '')
      const dateB = String(b.period_start ?? b.date ?? b.period ?? '')
      return dateA.localeCompare(dateB)
    })
    result[period] = Object.fromEntries(Object.entries(fieldsByCurrency).map(([currency, fields]) => [
      currency, fields.map((field) => ({
        name: field.label,
        type: field.type ?? 'line',
        color: field.color,
        yAxisIndex: field.axis,
        valueFormat: field.valueFormat,
        area: field.area,
        smooth: field.type !== 'bar',
        data: rows.map((row: Record<string, any>) => [
          row.period ?? row.date ?? row.period_start,
          row[field.key] == null ? null : Number(row[field.key]),
        ]) as ChartPoint[],
      })),
    ]))
  }
  return result
}

export function makeSeries(
  documents: Record<string, AnalyticsDocument>,
  fields: SeriesField[],
) {
  return makeCurrencySeries(documents, { USD: fields })
}

export const periodNames: Record<string, string> = {
  all_time: 'All time', daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly', quarterly: 'Quarterly', yearly: 'Yearly',
}
