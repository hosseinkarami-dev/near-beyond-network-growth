<script setup lang="ts">
import { computed } from 'vue'
import { formatCompact } from '~/composables/useAnalytics'

type ValidatorRow = {
  rank: number
  account_id: string
  stake_near: number | string | null
  stake_share: number | string | null
  commission_pct: number | string | null
  delegators_count: number | null
  block_production_rate: number | string | null
}

const props = defineProps<{ items: ValidatorRow[] }>()
const topItems = computed(() => props.items.slice(0, 10))

function formatRate(value: number | string | null) {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  return Number.isFinite(amount) ? `${amount.toFixed(2)}%` : '—'
}
</script>

<template>
  <section class="panel-card validator-table-card">
    <header class="panel-header">
      <div>
        <h2>Top validators by active stake</h2>
        <p>Ranked by current active stake · sourced from NearBlocks</p>
      </div>
    </header>
    <div class="validator-table-scroll">
      <table class="validator-table">
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Validator</th>
            <th scope="col" class="numeric">Active stake</th>
            <th scope="col" class="numeric">Stake share</th>
            <th scope="col" class="numeric">Commission</th>
            <th scope="col" class="numeric">Delegators</th>
            <th scope="col" class="numeric">Block production</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in topItems" :key="row.account_id">
            <td><span class="validator-rank">{{ String(row.rank).padStart(2, '0') }}</span></td>
            <td class="validator-account">
              <a :href="`https://nearblocks.io/address/${encodeURIComponent(row.account_id)}`" target="_blank" rel="noreferrer">{{ row.account_id }}</a>
            </td>
            <td class="numeric">{{ row.stake_near == null ? '—' : `${formatCompact(row.stake_near, 2)} NEAR` }}</td>
            <td class="numeric">{{ formatRate(row.stake_share) }}</td>
            <td class="numeric">{{ formatRate(row.commission_pct) }}</td>
            <td class="numeric">{{ row.delegators_count == null ? '—' : formatCompact(row.delegators_count, 0) }}</td>
            <td class="numeric">{{ formatRate(row.block_production_rate) }}</td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="7" class="validator-table-empty">No validator records are available.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
