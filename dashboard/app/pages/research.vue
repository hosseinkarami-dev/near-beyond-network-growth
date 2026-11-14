<script setup lang="ts">
import { ArrowRight, BookOpenCheck, Database, Scale, TrendingUp } from '@lucide/vue'
import { fetchAnalyticsOrEmpty, formatCompact, formatCurrency } from '~/composables/useAnalytics'
import { onBeforeUnmount, onMounted, ref } from 'vue'

const analyticsBaseUrl = useRuntimeConfig().public.analyticsBaseUrl as string
const paths = ['dashboard.json', 'network/snapshot.json', 'tokenomics/snapshot.json', 'tokenomics/daily_buyback_transfers.json', 'near_intents/snapshot.json', 'protocols/revenue/snapshot.json']
const { data, pending, error, refresh } = await useAsyncData('research-methodology-data', async () => {
  const documents = await Promise.all(paths.map((path) => fetchAnalyticsOrEmpty(path, analyticsBaseUrl)))
  return Object.fromEntries(paths.map((path, index) => [path, documents[index]]))
}, { server: false })
const doc = (path: string) => data.value?.[path]
const tokenomics = computed(() => doc('tokenomics/snapshot.json'))
const network = computed(() => doc('network/snapshot.json'))
const buybackRows = computed(() => doc('tokenomics/daily_buyback_transfers.json')?.observations ?? [])
const buybackCoverage = computed(() => tokenomics.value?.data_quality?.buyback_transfers)
const intents = computed(() => doc('near_intents/snapshot.json'))
const protocolRevenue = computed(() => doc('protocols/revenue/snapshot.json')?.summary)
const methods = computed(() => doc('dashboard.json')?.methodologies)
const updated = computed(() => doc('dashboard.json')?.latest_data_update)
const fmtPct = (value: unknown) => {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  return Number.isFinite(amount) ? `${amount.toFixed(2)}%` : '—'
}
const researchSections = [
  { id: 'thesis', label: 'Thesis' },
  { id: 'framework', label: 'Framework' },
  { id: 'methodology', label: 'Methodology' },
  { id: 'findings', label: 'Findings' },
  { id: 'implications', label: 'Implications' },
  { id: 'reproducibility', label: 'Sources & reproducibility' },
]
const activeSection = ref('thesis')
let scrollFrame = 0
let pendingSection: string | null = null
let settleTimer: ReturnType<typeof setTimeout> | undefined
function cancelPendingSection() {
  pendingSection = null
  if (settleTimer) clearTimeout(settleTimer)
}
function scheduleSectionActivation() {
  if (settleTimer) clearTimeout(settleTimer)
  settleTimer = setTimeout(() => {
    if (pendingSection) activeSection.value = pendingSection
    pendingSection = null
    settleTimer = undefined
  }, 220)
}
function syncActiveSection() {
  if (scrollFrame) cancelAnimationFrame(scrollFrame)
  scrollFrame = requestAnimationFrame(() => {
    if (pendingSection) {
      scheduleSectionActivation()
      return
    }
    const stickyTop = window.innerWidth <= 760 ? 68 : 76
    const tocHeight = document.querySelector<HTMLElement>('.research-toc')?.offsetHeight ?? 0
    const activationLine = stickyTop + tocHeight + 18
    let current = researchSections[0]?.id ?? 'thesis'
    for (const section of researchSections) {
      const element = document.getElementById(section.id)
      if (element && element.getBoundingClientRect().top <= activationLine) current = section.id
    }
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) {
      current = researchSections.at(-1)?.id ?? current
    }
    activeSection.value = current
  })
}
function scrollToSection(id: string) {
  const element = document.getElementById(id)
  if (!element) return
  pendingSection = id
  scheduleSectionActivation()
  if (window.location.hash !== `#${id}`) window.history.pushState(null, '', `#${id}`)
  const behavior: ScrollBehavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
  const stickyTop = window.innerWidth <= 760 ? 68 : 76
  const tocHeight = document.querySelector<HTMLElement>('.research-toc')?.offsetHeight ?? 0
  const top = window.scrollY + element.getBoundingClientRect().top - stickyTop - tocHeight - 10
  window.scrollTo({ top, behavior })
}
onMounted(() => {
  syncActiveSection()
  window.addEventListener('scroll', syncActiveSection, { passive: true })
  window.addEventListener('resize', syncActiveSection, { passive: true })
  window.addEventListener('wheel', cancelPendingSection, { passive: true })
  window.addEventListener('touchstart', cancelPendingSection, { passive: true })
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', syncActiveSection)
  window.removeEventListener('resize', syncActiveSection)
  window.removeEventListener('wheel', cancelPendingSection)
  window.removeEventListener('touchstart', cancelPendingSection)
  if (scrollFrame) cancelAnimationFrame(scrollFrame)
  if (settleTimer) clearTimeout(settleTimer)
})
</script>

<template>
  <PageLoadingSkeleton v-if="pending || !data" :metrics="3" :charts="3" />
  <DataLoadError v-else-if="error" title="Research data could not be loaded" :message="error.message" :retrying="pending" @retry="refresh" />
  <template v-else>
    <PageHeading eyebrow="RESEARCH &amp; METHODOLOGY" title="Beyond Network Growth" description="Does NEAR’s ecosystem growth translate into durable economic value and meaningful value capture?" :updated-at="updated" />

    <nav class="research-toc" aria-label="Research page sections">
      <a v-for="section in researchSections" :key="section.id" :href="`#${section.id}`" :class="{ active: activeSection === section.id }" :aria-current="activeSection === section.id ? 'location' : undefined" @click.prevent="scrollToSection(section.id)">{{ section.label }}</a>
    </nav>

    <section id="thesis" class="research-section panel-card">
      <div class="research-section-heading"><span class="research-icon"><BookOpenCheck :size="18" /></span><div><p class="eyebrow">01 · INVESTMENT THESIS</p><h2>Research question</h2></div></div>
      <p class="research-lead">NEAR’s ecosystem is growing across network activity, applications, and cross-chain liquidity. This research examines whether that growth is translating into measurable and sustainable economic value for the network and its token holders.</p>
      <p>Across network adoption, protocol economics, NEAR Intents, and tokenomics, we analyze reported activity, fees and revenue, issuance and fee burns, staking and validator participation, and buyback-related wallet flows. We distinguish observed activity and fund flows from confirmed value capture, and make the assumptions and limitations of each measure explicit.</p>
      <div class="research-callout"><strong>The central question</strong><span>Is NEAR’s ecosystem growth being matched by durable economic value and meaningful value capture, while its token economics support long-term sustainability?</span></div>
    </section>

    <section id="framework" class="research-section">
      <div class="research-section-heading"><span class="research-icon"><Scale :size="18" /></span><div><p class="eyebrow">02 · RESEARCH FRAMEWORK</p><h2>Four connected research areas</h2></div></div>
      <div class="research-framework-grid">
        <article class="panel-card research-topic"><span>01</span><h3>Network</h3><p>Adoption, usage, transaction activity, accounts, throughput, and liquidity on NEAR.</p><NuxtLink to="/network">Explore Network <ArrowRight :size="13" /></NuxtLink></article>
        <article class="panel-card research-topic"><span>02</span><h3>Protocols</h3><p>Economic activity, fees, reported revenue, and DEX volume across the ecosystem.</p><NuxtLink to="/protocols">Explore Protocols <ArrowRight :size="13" /></NuxtLink></article>
        <article class="panel-card research-topic"><span>03</span><h3>NEAR Intents</h3><p>Cross-chain volume and TVL, reported fees and revenue, holder allocation, and related wallet fund flows.</p><NuxtLink to="/intents">Explore NEAR Intents <ArrowRight :size="13" /></NuxtLink></article>
        <article class="panel-card research-topic"><span>04</span><h3>Tokenomics &amp; staking</h3><p>Issuance, fee burns, supply dynamics, active stake, validator participation, and concentration.</p><NuxtLink to="/tokenomics">Explore Tokenomics <ArrowRight :size="13" /></NuxtLink></article>
      </div>
      <div class="research-flow" aria-label="Research process"><span>Research question</span><i>→</i><span>Data</span><i>→</i><span>Methodology</span><i>→</i><span>Evidence</span><i>→</i><span>Findings</span><i>→</i><span>Implications</span></div>
    </section>

    <section id="methodology" class="research-section">
      <div class="research-section-heading"><span class="research-icon"><Database :size="18" /></span><div><p class="eyebrow">03 · METHOD</p><h2>Metric definitions and assumptions</h2></div></div>
      <p class="research-intro">The analysis follows the central question: whether observed growth is accompanied by durable revenue, value capture, and sustainable token economics. Collectors preserve provider responses, normalization standardizes them, and Analytics calculates the measures and period totals shown here. The dashboard displays those outputs without recalculating them.</p>
      <div class="research-method-grid">
        <article class="panel-card research-method"><h3>Network activity and liquidity</h3><p>Transactions, active accounts, active contracts, and contract creation are reported as daily observations. The dashboard’s 24-hour and 7-/30-day comparisons use exact calendar-date windows from Analytics; they describe activity, not unique people or economic value by themselves.</p><p>NEAR network TVL, NEAR Intents TVL, and stablecoin supply are point-in-time USD snapshots. Period views select an observation from the period rather than summing balances. These series can cover overlapping assets and must not be added together.</p><p>For NEAR-denominated network fees and TVL, the project divides or multiplies by the same UTC date’s Binance NEARUSDT closing price. USDT is a practical USD proxy, not an independently verified USD conversion.</p><p class="research-source">Sources: NearBlocks network endpoints, DefiLlama chain TVL and stablecoin datasets, and Binance daily NEARUSDT closes.</p><MethodologyTip v-if="methods?.network?.stablecoin_supply" :items="[methods.network.transaction_fees, methods.network.tvl, methods.network.stablecoin_supply].filter(Boolean)" /></article>

        <article class="panel-card research-method"><h3>Protocol economics and Intents value capture</h3><p><strong>NEAR Intents revenue capture · 30D</strong> is <code>(sum of daily NEAR Intents revenue over the trailing 30 dates ÷ sum of gross fees over those same dates) × 100</code>. It is a ratio of sums, not an average of daily percentages. Analytics requires a complete window and does not cap the result at 100%.</p><p>Revenue and gross fees are separate provider series and may not reconcile day by day. Periodic wallet sweeps can shift the timing of reported revenue, so a short window is sensitive to recognition timing. Holders revenue is a separate allocation series; it is not added again to revenue.</p><p>The Overview’s <em>NEAR ecosystem revenue</em> is the aggregate returned by DefiLlama’s NEAR <code>dailyRevenue</code> endpoint. Its protocol breakdown includes NEAR Intents where reported, so it overlaps the Intents-specific revenue metric. Treat these as provider classifications, not as audited cash flow to every NEAR holder.</p><p class="research-source">Sources: DefiLlama NEAR Intents volume, fees, revenue and holders-revenue breakdowns, plus the broader NEAR revenue breakdown.</p><MethodologyTip v-if="methods?.near_intents?.revenue_capture_rate_30d" :items="[methods.near_intents.volume, methods.near_intents.gross_fees, methods.near_intents.revenue, methods.near_intents.revenue_capture_rate_30d].filter(Boolean)" /></article>

        <article class="panel-card research-method"><h3>Supply expansion, burns, and issuance</h3><p><strong>Net issuance (daily)</strong> is the change between consecutive period-end total-supply observations: <code>Total supply(D) − Total supply(D−1)</code>. A missing previous date leaves the change blank.</p><p><strong>Net fee burn</strong> is <code>execution_outcomes.tokens_burnt − contract rewards</code>. The project uses <code>tokens_burnt</code> as reported; it does not reconstruct burn as gas burnt times gas price. That source field can include additional token-burn components and may differ from the gas-price product.</p><p><strong>Estimated gross issuance</strong> is <code>net issuance + net fee burn</code>. It is inferred from supply change and burn, not fetched as a validator-reward total. Missing burn or supply inputs leave it blank.</p><p><strong>Annualized net inflation · 30D</strong> is compounded from total supply at D and D−30: <code>((supply(D) / supply(D−30))^(365/30) − 1) × 100</code>. It measures net supply growth, including burn effects. <strong>Burn Coverage</strong> is the period’s summed net fee burn divided by summed estimated gross issuance.</p><p>Zero contract rewards are assigned only to dates in a complete audit with no reward events and to dates on or after the project’s protocol-v87 zero-policy start. Other unavailable reward dates remain null.</p><p class="research-source">Sources: BigQuery public NEAR mainnet <code>daily_supply</code>, <code>daily_gross_burn</code>, and <code>contract_reward_event_audit</code>. Supply is approximate FLOAT64; issuance is an estimate and may not reconcile exactly if the supply series includes unmodeled adjustments.</p><MethodologyTip v-if="methods?.tokenomics?.supply_dynamics" :items="[methods.tokenomics.supply_dynamics, methods.tokenomics.net_burn, methods.tokenomics.net_inflation, methods.tokenomics.burn_coverage]" /></article>

        <article class="panel-card research-method"><h3>Staking and validator security</h3><p><strong>Staking ratio · circulating supply</strong> is the NearBlocks current active stake divided by the latest available circulating-supply observation, multiplied by 100. The numerator is a current snapshot and can be one calendar day newer than the approximate FLOAT64 supply denominator. The historical stake chart instead divides each daily stake observation by that date’s <strong>total</strong> supply; those are different ratios.</p><p><strong>Top 10 stake share</strong> is the combined stake of the ten largest active validators divided by total active validator stake. It measures concentration within reported active stake, not the share of circulating supply or the number of independent operators.</p><p>Historical daily stake uses each daily-supply block height, resolves its epoch through FastNEAR RPC, sums current validator stakes using arbitrary-precision integers, then converts YoctoNEAR to NEAR. The first configured collection window is three calendar months before the run; existing checkpointed data is retained and collection continues after its latest saved date. Period views select the last available snapshot and are not cumulative.</p><p>When the validator list is incomplete, analytics leaves aggregates that require full registry coverage (such as HHI, total delegators, weighted average commission, and network-wide block-production rate) blank. Delegator counts may also double-count accounts delegated to multiple validators.</p><p class="research-source">Sources: NearBlocks current validator endpoints, BigQuery daily supply, and FastNEAR archival RPC.</p><MethodologyTip v-if="methods?.tokenomics?.staking" :items="[methods.tokenomics.staking, methods.tokenomics.validators, methods.tokenomics.historical_active_stake]" /></article>

        <article class="panel-card research-method"><h3>Buyback-wallet fund flows</h3><p>The transfer query records native NEAR transfers and wNEAR <code>ft_transfer</code> events into <code>buybacks.multisignature.near</code>, grouped by sender and the transfer type returned by BigQuery. Analytics converts those rows to daily and calendar-period inflows. The wallet-balance card shows the liquid <code>amount</code> from a finalized FastNEAR RPC account view, excluding locked stake.</p><p>An incoming transfer is not evidence that NEAR was bought on the market. These records do not reveal execution price, amount purchased, custody movements after receipt, or a token burn. The current analytics sample starts {{ buybackRows[0]?.date ?? '—' }} and ends {{ buybackCoverage?.latest_date ?? '—' }}; do not read the sample total as an all-time figure.</p><p class="research-source">Source: BigQuery buyback transfer query (configured start date 2026-04-01); FastNEAR finalized RPC wallet balance. Daily, weekly, monthly, quarterly, and yearly flows are sums within their respective period, not cumulative balances.</p><MethodologyTip v-if="methods?.tokenomics?.buybacks" :items="methods.tokenomics.buybacks" /></article>
      </div>
    </section>

    <section id="findings" class="research-section">
      <div class="research-section-heading"><span class="research-icon"><TrendingUp :size="18" /></span><div><p class="eyebrow">04 · OBSERVED EVIDENCE</p><h2>Key findings</h2></div></div>
      <p class="research-intro">Values below are taken directly from the generated analytics snapshots. Their source dates differ by metric; each date is shown to avoid implying a single synchronized observation.</p>
      <div class="metric-grid dashboard-metrics dashboard-metrics-three research-findings-grid">
        <MetricCard label="NEAR Intents volume · 30D" :value="formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1)" :detail="`Through ${intents?.key_metrics?.volume_usd?.date ?? '—'} · ${fmtPct(intents?.key_metrics?.volume_usd?.change_30d_pct)} vs prior 30D`" :change-label="''" />
        <MetricCard label="NEAR Intents revenue capture · 30D" :value="fmtPct(intents?.key_metrics?.revenue_capture_rate_30d_pct?.value)" :detail="`As of ${intents?.key_metrics?.revenue_capture_rate_30d_pct?.date ?? '—'}`" :change-label="''" />
        <MetricCard label="NEAR Intents revenue · 30D" :value="formatCurrency(intents?.key_metrics?.revenue_usd?.total_30d, 'USD', 1, 1)" :detail="`Through ${intents?.key_metrics?.revenue_usd?.date ?? '—'} · ${fmtPct(intents?.key_metrics?.revenue_usd?.change_30d_pct)} vs prior 30D`" :change-label="''" />
        <MetricCard label="NEAR ecosystem revenue · 30D" :value="formatCurrency(protocolRevenue?.total_30d, 'USD', 1, 1)" :detail="`As of ${doc('protocols/revenue/snapshot.json')?.updated_at?.slice(0, 10) ?? '—'} · ${fmtPct(protocolRevenue?.growth_30d)} vs prior 30D · includes Intents`" :change-label="''" />
        <MetricCard label="Annualized net inflation · 30D" :value="fmtPct(tokenomics?.metrics?.net_inflation_30d_annualized_pct)" :detail="`Supply through ${tokenomics?.data_quality?.daily_supply?.latest_date ?? '—'}`" :change-label="''" />
        <MetricCard label="Estimated gross issuance · 30D" :value="`${formatCompact(tokenomics?.metrics?.gross_issuance_30d_near, 2)} NEAR`" :detail="`Net fee burn ${formatCompact(tokenomics?.metrics?.net_burn_30d_near, 2)} NEAR · supply through ${tokenomics?.data_quality?.daily_supply?.latest_date ?? '—'}`" :change-label="''" />
        <MetricCard label="Burn coverage · 30D" :value="fmtPct(tokenomics?.metrics?.burn_offset_30d_pct)" :detail="`Through ${tokenomics?.data_quality?.daily_gross_burn?.latest_date ?? '—'}`" :change-label="''" />
        <MetricCard label="Staking ratio · circulating supply" :value="fmtPct(tokenomics?.metrics?.staking_ratio)" :detail="`${formatCompact(tokenomics?.metrics?.total_active_stake, 1)} NEAR active stake · as of ${tokenomics?.metrics?.total_active_stake_as_of_date ?? '—'}`" :change-label="''" />
        <MetricCard label="Top 10 stake share" :value="fmtPct(tokenomics?.metrics?.top_10_stake_share)" :detail="`${formatCompact(tokenomics?.metrics?.active_validators_count, 0)} active validators · as of ${tokenomics?.metrics?.total_active_stake_as_of_date ?? '—'}`" :change-label="''" />
      </div>
      <div class="research-findings-notes">
        <article><h3>Usage is growing; liquidity is mixed</h3><p>In the latest network snapshot, transactions are up {{ fmtPct(network?.key_metrics?.transactions?.change_30d_pct) }} and active accounts are up {{ fmtPct(network?.key_metrics?.active_accounts?.change_30d_pct) }} over 30 days. Over the same comparison window, network TVL is down {{ fmtPct(network?.key_metrics?.tvl_usd?.change_30d_pct) }}, while stablecoin supply is up {{ fmtPct(network?.key_metrics?.stablecoin_supply_usd?.change_30d_pct) }}. NEAR Intents TVL is down {{ fmtPct(intents?.key_metrics?.tvl_usd?.change_30d_pct) }}. Adoption and capital depth are therefore sending different signals.</p></article>
        <article><h3>Recent Intents monetization has softened</h3><p>Reported 30-day Intents volume is {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1) }} and is {{ fmtPct(intents?.key_metrics?.volume_usd?.change_30d_pct) }} versus the previous window. Reported revenue is {{ formatCurrency(intents?.key_metrics?.revenue_usd?.total_30d, 'USD', 1, 1) }} ({{ fmtPct(intents?.key_metrics?.revenue_usd?.change_30d_pct) }}), against {{ formatCurrency(intents?.key_metrics?.gross_fees_usd?.total_30d, 'USD', 1, 1) }} in gross fees ({{ fmtPct(intents?.key_metrics?.gross_fees_usd?.change_30d_pct) }}). The {{ fmtPct(intents?.key_metrics?.revenue_capture_rate_30d_pct?.value) }} capture ratio is a provider-series ratio, not a holder yield. Ecosystem revenue is a wider series that includes Intents and must not be added to Intents revenue.</p></article>
        <article><h3>Supply growth currently outweighs fee-burn offset</h3><p>Total supply rose by {{ formatCompact(tokenomics?.metrics?.net_supply_change_30d_near, 2) }} NEAR in the latest 30-day window ({{ fmtPct(tokenomics?.metrics?.net_supply_growth_30d_pct) }} net growth; {{ fmtPct(tokenomics?.metrics?.net_inflation_30d_annualized_pct) }} annualized). Estimated gross issuance was {{ formatCompact(tokenomics?.metrics?.gross_issuance_30d_near, 2) }} NEAR and net fee burn was {{ formatCompact(tokenomics?.metrics?.net_burn_30d_near, 2) }} NEAR, giving {{ fmtPct(tokenomics?.metrics?.burn_offset_30d_pct) }} Burn Coverage. The issuance estimate is a supply reconciliation, not a direct reward count.</p></article>
        <article><h3>Stake is substantial, but concentration and coverage matter</h3><p>NearBlocks reports {{ formatCompact(tokenomics?.metrics?.total_active_stake, 2) }} NEAR across {{ formatCompact(tokenomics?.metrics?.active_validators_count, 0) }} active validators ({{ formatCompact(tokenomics?.metrics?.total_validators_count, 0) }} registered). The top ten hold {{ fmtPct(tokenomics?.metrics?.top_10_stake_share) }} of active stake and the largest holds {{ fmtPct(tokenomics?.metrics?.top_1_stake_share) }}. The current stake snapshot is dated {{ tokenomics?.metrics?.total_active_stake_as_of_date ?? '—' }}, while its circulating-supply denominator is dated {{ tokenomics?.data_quality?.daily_supply?.latest_date ?? '—' }}. HHI and other network-wide aggregates are blank where validator registry coverage is incomplete. These data do not establish independent operator ownership.</p></article>
        <article><h3>Wallet records stop at inflows</h3><p>The available transfer series currently spans {{ buybackRows[0]?.date ?? '—' }} to {{ buybackCoverage?.latest_date ?? '—' }}; the wallet’s liquid balance is {{ formatCompact(tokenomics?.metrics?.buyback_wallet_balance_near, 2) }} NEAR as of {{ tokenomics?.metrics?.buyback_wallet_balance_date ?? '—' }}. Neither the inflow chart nor this balance shows whether NEAR was purchased or who ultimately holds any purchased tokens.</p></article>
      </div>
      <div class="research-link-row"><NuxtLink to="/intents">Inspect Intents evidence <ArrowRight :size="13" /></NuxtLink><NuxtLink to="/tokenomics">Inspect supply and staking <ArrowRight :size="13" /></NuxtLink><NuxtLink to="/protocols">Inspect protocol revenue <ArrowRight :size="13" /></NuxtLink></div>
    </section>

    <section id="implications" class="research-section panel-card">
      <div class="research-section-heading"><span class="research-icon"><Scale :size="18" /></span><div><p class="eyebrow">05 · INTERPRETATION</p><h2>Investment implications</h2></div></div>
      <div class="research-implications-grid">
        <div><h3>Evidence in favour</h3><ul><li>Transactions are up {{ fmtPct(network?.key_metrics?.transactions?.change_30d_pct) }} and active accounts are up {{ fmtPct(network?.key_metrics?.active_accounts?.change_30d_pct) }} over the latest 30-day network comparison; stablecoin supply is also higher.</li><li>NEAR Intents reports {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1) }} in 30-day volume, alongside fee, revenue, and holders-revenue series that make reported value allocation measurable.</li><li>{{ formatCompact(tokenomics?.metrics?.total_active_stake, 0) }} NEAR is reported staked across {{ formatCompact(tokenomics?.metrics?.active_validators_count, 0) }} active validators; the top validator’s reported share is {{ fmtPct(tokenomics?.metrics?.top_1_stake_share) }}.</li></ul></div>
        <div><h3>Evidence that limits the case</h3><ul><li>Network TVL and NEAR Intents TVL are down {{ fmtPct(network?.key_metrics?.tvl_usd?.change_30d_pct) }} and {{ fmtPct(intents?.key_metrics?.tvl_usd?.change_30d_pct) }} respectively; recent Intents volume, fees, and revenue are also lower.</li><li>Net supply increased by {{ formatCompact(tokenomics?.metrics?.net_supply_change_30d_near, 2) }} NEAR in the latest 30 days. Net fee burn offset {{ fmtPct(tokenomics?.metrics?.burn_offset_30d_pct) }} of estimated gross issuance in that window.</li><li>The {{ fmtPct(intents?.key_metrics?.revenue_capture_rate_30d_pct?.value) }} Intents revenue-capture rate is provider-based and timing-sensitive; it is not a direct yield to NEAR holders. Wallet inflows are not verified purchases.</li><li>Supply precision is approximate, current stake and supply dates can differ, and incomplete validator metadata prevents some concentration and performance aggregates.</li></ul></div>
      </div>
      <p class="research-conclusion"><strong>Assessment:</strong> the data support the claim that NEAR has meaningful and growing network use: transactions and active accounts are higher over 30 days, and Intents processed {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1) }} in reported volume. But the economic follow-through is not yet convincing. Intents revenue fell {{ fmtPct(intents?.key_metrics?.revenue_usd?.change_30d_pct) }} over its prior 30-day window, network TVL fell {{ fmtPct(network?.key_metrics?.tvl_usd?.change_30d_pct) }}, and supply rose by {{ formatCompact(tokenomics?.metrics?.net_supply_change_30d_near, 2) }} NEAR. Fee burn covered only {{ fmtPct(tokenomics?.metrics?.burn_offset_30d_pct) }} of estimated gross issuance. Staking is material, but concentration data alone cannot establish independent validator control or token-holder returns. On balance, the current evidence shows ecosystem growth without yet demonstrating durable, broad-based value capture. That is a qualified negative finding on the value-capture question—not a conclusion about NEAR’s market price or future investment return. Provider definitions, asynchronous source dates, approximate supply precision, incomplete validator metadata, and the lack of proof linking wallet inflows to completed purchases limit what can be inferred.</p>
    </section>

    <section id="reproducibility" class="research-section panel-card">
      <div class="research-section-heading"><span class="research-icon"><Database :size="18" /></span><div><p class="eyebrow">06 · DATA &amp; REPRODUCIBILITY</p><h2>Sources, ranges, and refresh process</h2></div></div>
      <div class="research-source-grid">
        <div><h3>Provider datasets</h3><ul><li><strong>NearBlocks:</strong> network stats and current validator data; fetched incrementally where the source supports historical dates.</li><li><strong>DefiLlama:</strong> stablecoin supply, NEAR Intents volume/TVL/revenue/fees, broader NEAR revenue breakdown, and DEX volume.</li><li><strong>Google BigQuery public NEAR mainnet:</strong> daily supply snapshots, execution-outcome <code>tokens_burnt</code>, contract-reward event audit, and buyback transfer records.</li><li><strong>Binance:</strong> daily NEARUSDT closes used as the project’s USD price proxy.</li><li><strong>FastNEAR archival RPC:</strong> historical active validator stake and finalized buyback wallet balance.</li></ul></div>
        <div><h3>Project resources and update cadence</h3><ul><li>Raw provider responses are under <code>data/raw/</code>; parser outputs are under <code>data/normalized/</code>; dashboard-ready datasets are under <code>data/analytics/</code>.</li><li>Dataset-specific definitions and data coverage are maintained in <code>docs/analytics/</code>, especially <code>tokenomics.md</code> and <code>network.md</code>.</li><li>Run <code>py scripts/main.py</code> from the repository root to fetch, normalize, and build analytics. The historical validator-stake collector runs last because it uses block heights in raw BigQuery <code>daily_supply.json</code>.</li><li>Run <code>py scripts/build_analytics.py</code> to rebuild Analytics from existing normalized files without fetching. It syncs the new Analytics files to the dashboard at the end. From <code>dashboard/</code>, <code>npm run sync:data</code> remains available for a manual sync.</li><li>Daily sources use successful-request cooldowns and resume from their latest raw dates; the current UTC day is not queried as a completed daily observation. Failed sources remain eligible for retry. See the README for credentials, local setup, and provider details.</li></ul></div>
      </div>
      <p class="research-source">Coverage in this Analytics snapshot is not uniform: total-supply observations span {{ tokenomics?.data_quality?.daily_supply?.start_date ?? '—' }} through {{ tokenomics?.data_quality?.daily_supply?.latest_date ?? '—' }} ({{ formatCompact(tokenomics?.data_quality?.daily_supply?.observations, 0) }} observations; {{ formatCompact(tokenomics?.data_quality?.daily_supply?.missing_calendar_dates, 0) }} missing calendar dates). Exact historical validator stake spans {{ tokenomics?.data_quality?.daily_active_validator_stake?.start_date ?? '—' }} through {{ tokenomics?.data_quality?.daily_active_validator_stake?.latest_date ?? '—' }}. Gross-burn records span {{ tokenomics?.data_quality?.daily_gross_burn?.start_date ?? '—' }} through {{ tokenomics?.data_quality?.daily_gross_burn?.latest_date ?? '—' }} and have {{ formatCompact(tokenomics?.data_quality?.daily_gross_burn?.missing_calendar_dates, 0) }} missing dates. The configured contract-reward audit defaults to 2026-01-01 through 2026-10-04; the current cached raw audit was experimentally extended through 2026-11-13, while Analytics applies the project’s protocol-v87 zero policy from 2026-11-05. Missing inputs remain blank unless a documented completeness rule supports zero.</p>
      <p class="research-source">Data snapshot last updated {{ updated ?? '—' }}. Values may carry source-specific timestamps and precision. Use the timestamp attached to each metric and the data-quality metadata before comparing periods.</p>
    </section>
  </template>
</template>
