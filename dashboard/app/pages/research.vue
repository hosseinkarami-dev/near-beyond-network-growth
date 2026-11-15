<script setup lang="ts">
import { Activity, ArrowLeftRight, BookOpenCheck, ChartNoAxesCombined, CircleDollarSign, Coins, Database, Flame, Layers3, Scale, Shield, TrendingUp, UsersRound } from '@lucide/vue'
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
      <p class="research-lead">NEAR’s activity spans network use, applications, and cross-chain liquidity. This research asks whether that activity is producing durable economic value for the network and its token holders.</p>
      <p>The dashboard follows four areas: network adoption, protocol economics, NEAR Intents, and tokenomics. It compares activity with reported fees and revenue, supply growth and burns, staking, and transfers to the buyback wallet. A reported fee, a wallet transfer, and a completed purchase are recorded as different events.</p>
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
      <p class="research-intro">The figures on this page are produced in Analytics. Collectors save provider responses; normalization validates and standardizes them; Analytics joins the inputs and calculates metrics and period totals. The dashboard displays those results.</p>
      <div class="research-method-grid">
        <article class="panel-card research-method"><h3>Network activity and liquidity</h3><p>Transactions, active accounts, active contracts, and new contracts are daily counts. The 24-hour and 7-/30-day comparisons use set calendar windows. An active account is an account seen on-chain; it should not be read as a unique person or as economic value on its own.</p><p>TVL and stablecoin supply are point-in-time balances, not flows. Period charts use an observation from the period rather than adding daily balances. NEAR TVL, Intents TVL, and stablecoin supply may overlap, so they should not be summed.</p><p>Where a NEAR amount is shown in USD, Analytics uses that UTC date’s Binance NEARUSDT close. USDT is the project’s price proxy; it is not an independent USD conversion.</p><p class="research-source">Sources: NearBlocks network endpoints, DefiLlama chain TVL and stablecoin datasets, and Binance daily NEARUSDT closes.</p><MethodologyTip v-if="methods?.network?.stablecoin_supply" :items="[methods.network.transaction_fees, methods.network.tvl, methods.network.stablecoin_supply].filter(Boolean)" /></article>

        <article class="panel-card research-method"><h3>Protocol economics and Intents value capture</h3><p><strong>NEAR Intents revenue capture · 30D</strong> is <code>(sum of daily NEAR Intents revenue over the trailing 30 dates ÷ sum of gross fees over those same dates) × 100</code>. It is a ratio of sums, not an average of daily percentages. Analytics requires a complete window and does not cap the result at 100%.</p><p>Fees and revenue come from separate provider series and do not have to line up on each date. Revenue sweeps can shift reported revenue between days. The holders-revenue series is shown separately and is not added to revenue again.</p><p>The Overview’s <em>NEAR ecosystem revenue</em> comes from DefiLlama’s NEAR <code>dailyRevenue</code> endpoint. That breakdown includes NEAR Intents where reported, so the two revenue cards overlap and must not be added together. These are provider-reported classifications, not audited cash paid to each NEAR holder.</p><p class="research-source">Sources: DefiLlama NEAR Intents volume, fees, revenue and holders-revenue breakdowns, plus the broader NEAR revenue breakdown.</p><MethodologyTip v-if="methods?.near_intents?.revenue_capture_rate_30d" :items="[methods.near_intents.volume, methods.near_intents.gross_fees, methods.near_intents.revenue, methods.near_intents.revenue_capture_rate_30d].filter(Boolean)" /></article>

        <article class="panel-card research-method"><h3>Supply expansion, burns, and issuance</h3><p><strong>Net issuance (daily)</strong> is the change between consecutive period-end total-supply observations: <code>Total supply(D) − Total supply(D−1)</code>. A missing previous date leaves the change blank.</p><p><strong>Net fee burn</strong> is <code>execution_outcomes.tokens_burnt − contract rewards</code>. The project uses <code>tokens_burnt</code> as reported. It does not substitute <code>gas_burnt × gas_price</code>: the source field can include other burn components and can differ from that calculation.</p><p><strong>Estimated gross issuance</strong> is <code>net issuance + net fee burn</code>. It is inferred from supply change and burn, not fetched as a validator-reward total. Missing burn or supply inputs leave it blank.</p><p><strong>Annualized net inflation · 30D</strong> compounds total supply at D and D−30: <code>((supply(D) / supply(D−30))^(365/30) − 1) × 100</code>. It measures net supply growth, including burn effects. Burn, gross issuance, and Burn Coverage use the latest 30-day flow window for which daily supply changes and burn data are complete; its end date can be earlier than the latest supply date. Burn Coverage (%) is <code>(sum of net fee burn ÷ sum of estimated gross issuance) × 100</code> over that matched flow window.</p><p>Zero contract rewards are assigned only to dates in a complete audit with no reward events and to dates on or after the project’s protocol-v87 zero-policy start. Other unavailable reward dates remain null.</p><p class="research-source">Sources: BigQuery public NEAR mainnet <code>daily_supply</code>, <code>daily_gross_burn</code>, and <code>contract_reward_event_audit</code>. Supply is approximate FLOAT64; issuance is an estimate and may not reconcile exactly if the supply series includes unmodeled adjustments.</p><MethodologyTip v-if="methods?.tokenomics?.supply_dynamics" :items="[methods.tokenomics.supply_dynamics, methods.tokenomics.net_burn, methods.tokenomics.net_inflation, methods.tokenomics.burn_coverage]" /></article>

        <article class="panel-card research-method"><h3>Staking and validator security</h3><p><strong>Staking ratio · circulating supply</strong> is the NearBlocks current active stake divided by the latest available circulating-supply observation, multiplied by 100. The numerator is a current snapshot and can be one calendar day newer than the approximate FLOAT64 supply denominator. The historical stake chart instead divides each daily stake observation by that date’s <strong>total</strong> supply; those are different ratios.</p><p><strong>Top 10 stake share</strong> is the combined stake of the ten largest active validators divided by total active validator stake. This is concentration within reported active stake. It is not a share of circulating supply and says nothing about whether validators have independent operators.</p><p>Historical daily stake uses each daily-supply block height, resolves its epoch through FastNEAR RPC, sums current validator stakes using arbitrary-precision integers, then converts YoctoNEAR to NEAR. The first configured collection window is three calendar months before the run; existing checkpointed data is retained and collection continues after its latest saved date. Period views select the last available snapshot and are not cumulative.</p><p>When the validator list is incomplete, analytics leaves aggregates that require full registry coverage (such as HHI, total delegators, weighted average commission, and network-wide block-production rate) blank. Delegator counts may also double-count accounts delegated to multiple validators.</p><p class="research-source">Sources: NearBlocks current validator endpoints, BigQuery daily supply, and FastNEAR archival RPC.</p><MethodologyTip v-if="methods?.tokenomics?.staking" :items="[methods.tokenomics.staking, methods.tokenomics.validators, methods.tokenomics.historical_active_stake]" /></article>

        <article class="panel-card research-method"><h3>Buyback-wallet fund flows</h3><p>The BigQuery query identifies native NEAR transfers and wNEAR <code>ft_transfer</code> events into <code>buybacks.multisignature.near</code>. Analytics groups the returned amounts by date and transfer type. The wallet card is a separate finalized FastNEAR RPC reading of liquid balance; it excludes locked stake.</p><p>The available daily series attributes inflows to NEAR Intents and 1Click &amp; other revenue. It shows recurring Intents flows and more episodic 1Click; the largest daily amount in that category is 502,793 NEAR on September 9, 2026. This is an observed wallet inflow, not evidence of a completed purchase.</p><p>A transfer into the wallet does not show whether NEAR was bought, at what price, or where purchased tokens were later held. The available series runs from {{ buybackRows[0]?.date ?? '—' }} through {{ buybackCoverage?.latest_date ?? '—' }}; totals cover that sample only.</p><p class="research-source">Sources: BigQuery buyback transfer query (configured start date 2026-04-01), and FastNEAR finalized RPC wallet balance. Daily, weekly, monthly, quarterly, and yearly flows are sums within their respective period, not cumulative balances.</p><MethodologyTip v-if="methods?.tokenomics?.buybacks" :items="methods.tokenomics.buybacks" /></article>
      </div>
    </section>

    <section id="findings" class="research-section">
      <div class="research-section-heading"><span class="research-icon"><TrendingUp :size="18" /></span><div><p class="eyebrow">04 · OBSERVED EVIDENCE</p><h2>Key findings</h2></div></div>
      <div class="panel-card research-section-content">
      <p class="research-intro">The findings use the longer series where available and show the source date for each current metric. Thirty-day changes help describe recent momentum, but they do not establish a long-term trend or its cause. These datasets do not separate NEAR-specific changes from broader crypto-market moves.</p>
      <div class="metric-grid dashboard-metrics dashboard-metrics-three research-findings-grid">
        <MetricCard label="NEAR Intents volume · 30D" :value="formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1)" :detail="`Through ${intents?.key_metrics?.volume_usd?.date ?? '—'} · ${fmtPct(intents?.key_metrics?.volume_usd?.change_30d_pct)} vs prior 30D`" :change-label="''" :icon="ArrowLeftRight" tone="green" />
        <MetricCard label="NEAR Intents revenue capture · 30D" :value="fmtPct(intents?.key_metrics?.revenue_capture_rate_30d_pct?.value)" :detail="`As of ${intents?.key_metrics?.revenue_capture_rate_30d_pct?.date ?? '—'}`" :change-label="''" :icon="Activity" tone="violet" />
        <MetricCard label="NEAR Intents revenue · 30D" :value="formatCurrency(intents?.key_metrics?.revenue_usd?.total_30d, 'USD', 1, 1)" :detail="`Through ${intents?.key_metrics?.revenue_usd?.date ?? '—'} · ${fmtPct(intents?.key_metrics?.revenue_usd?.change_30d_pct)} vs prior 30D`" :change-label="''" :icon="Coins" tone="blue" />
        <MetricCard label="NEAR ecosystem revenue · 30D" :value="formatCurrency(protocolRevenue?.total_30d, 'USD', 1, 1)" :detail="`As of ${doc('protocols/revenue/snapshot.json')?.updated_at?.slice(0, 10) ?? '—'} · ${fmtPct(protocolRevenue?.growth_30d)} vs prior 30D · includes Intents`" :change-label="''" :icon="Layers3" tone="green" />
        <MetricCard label="Annualized net inflation · 30D" :value="fmtPct(tokenomics?.metrics?.net_inflation_30d_annualized_pct)" :detail="`Supply through ${tokenomics?.data_quality?.daily_supply?.latest_date ?? '—'}`" :change-label="''" :icon="TrendingUp" tone="amber" />
        <MetricCard label="Estimated gross issuance · 30D" :value="`${formatCompact(tokenomics?.metrics?.gross_issuance_30d_near, 2)} NEAR`" :detail="`Net fee burn ${formatCompact(tokenomics?.metrics?.net_burn_30d_near, 2)} NEAR · through ${tokenomics?.metrics?.latest_burn_coverage_date ?? '—'}`" :change-label="''" :icon="ChartNoAxesCombined" tone="amber" />
        <MetricCard label="Burn coverage · 30D" :value="fmtPct(tokenomics?.metrics?.burn_offset_30d_pct)" :detail="`Through ${tokenomics?.metrics?.latest_burn_coverage_date ?? '—'}`" :change-label="''" :icon="Flame" tone="blue" />
        <MetricCard label="Staking ratio · circulating supply" :value="fmtPct(tokenomics?.metrics?.staking_ratio)" :detail="`${formatCompact(tokenomics?.metrics?.total_active_stake, 1)} NEAR active stake · as of ${tokenomics?.metrics?.total_active_stake_as_of_date ?? '—'}`" :change-label="''" :icon="Shield" tone="green" />
        <MetricCard label="Top 10 stake share" :value="fmtPct(tokenomics?.metrics?.top_10_stake_share)" :detail="`${formatCompact(tokenomics?.metrics?.active_validators_count, 0)} active validators · as of ${tokenomics?.metrics?.total_active_stake_as_of_date ?? '—'}`" :change-label="''" :icon="UsersRound" tone="violet" />
      </div>
      <div class="research-findings-notes">
        <article><h3>Long-run usage is material, liquidity is mixed</h3><p>The network series extends back to 2021, while NEAR Intents volume is available from 2024. Intents has recorded {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_all_time, 'USD', 1) }} in total volume and {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_1y, 'USD', 1) }} over the trailing year. The latest 30-day comparisons add a shorter-term signal: transactions are up {{ fmtPct(network?.key_metrics?.transactions?.change_30d_pct) }} and active accounts are up {{ fmtPct(network?.key_metrics?.active_accounts?.change_30d_pct) }}, while network TVL is down {{ fmtPct(network?.key_metrics?.tvl_usd?.change_30d_pct) }} and stablecoin supply is up {{ fmtPct(network?.key_metrics?.stablecoin_supply_usd?.change_30d_pct) }}. NEAR Intents TVL is down {{ fmtPct(intents?.key_metrics?.tvl_usd?.change_30d_pct) }}. These 30-day changes describe recent momentum; they do not establish a lasting trend or its cause.</p></article>
        <article><h3>Volume scale is clearer than durable value capture</h3><p>Reported 30-day Intents volume is {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1) }} through {{ intents?.key_metrics?.volume_usd?.date ?? '—' }} ({{ fmtPct(intents?.key_metrics?.volume_usd?.change_30d_pct) }} versus the prior window). Reported revenue is {{ formatCurrency(intents?.key_metrics?.revenue_usd?.total_30d, 'USD', 1, 1) }} through {{ intents?.key_metrics?.revenue_usd?.date ?? '—' }} ({{ fmtPct(intents?.key_metrics?.revenue_usd?.change_30d_pct) }}), while gross fees are {{ formatCurrency(intents?.key_metrics?.gross_fees_usd?.total_30d, 'USD', 1, 1) }} through {{ intents?.key_metrics?.gross_fees_usd?.date ?? '—' }} ({{ fmtPct(intents?.key_metrics?.gross_fees_usd?.change_30d_pct) }}). The {{ fmtPct(intents?.key_metrics?.revenue_capture_rate_30d_pct?.value) }} capture ratio is a provider-series ratio, not a holder yield. These 30-day comparisons are short-term signals, not long-term verdicts. Revenue sweeps and movements in crypto markets can affect USD-denominated series. Ecosystem revenue includes Intents and must not be added to Intents revenue.</p></article>
        <article><h3>Supply growth currently outweighs fee-burn offset</h3><p>Total supply rose by {{ formatCompact(tokenomics?.metrics?.net_supply_change_30d_near, 2) }} NEAR over the 30 days through {{ tokenomics?.data_quality?.daily_supply?.latest_date ?? '—' }} ({{ fmtPct(tokenomics?.metrics?.net_supply_growth_30d_pct) }} net growth; {{ fmtPct(tokenomics?.metrics?.net_inflation_30d_annualized_pct) }} annualized). In the latest complete 30-day flow window through {{ tokenomics?.metrics?.latest_burn_coverage_date ?? '—' }}, estimated gross issuance was {{ formatCompact(tokenomics?.metrics?.gross_issuance_30d_near, 2) }} NEAR and net fee burn was {{ formatCompact(tokenomics?.metrics?.net_burn_30d_near, 2) }} NEAR; fee burn offset {{ fmtPct(tokenomics?.metrics?.burn_offset_30d_pct) }} of estimated gross issuance. The issuance estimate is a supply reconciliation, not a direct reward count.</p></article>
        <article><h3>Stake is substantial, but concentration and coverage matter</h3><p>NearBlocks reports {{ formatCompact(tokenomics?.metrics?.total_active_stake, 2) }} NEAR across {{ formatCompact(tokenomics?.metrics?.active_validators_count, 0) }} active validators ({{ formatCompact(tokenomics?.metrics?.total_validators_count, 0) }} registered). The top ten hold {{ fmtPct(tokenomics?.metrics?.top_10_stake_share) }} of active stake and the largest holds {{ fmtPct(tokenomics?.metrics?.top_1_stake_share) }}. The current stake snapshot is dated {{ tokenomics?.metrics?.total_active_stake_as_of_date ?? '—' }}, while its circulating-supply denominator is dated {{ tokenomics?.data_quality?.daily_supply?.latest_date ?? '—' }}. HHI and other network-wide aggregates are blank where validator registry coverage is incomplete. These data do not establish independent operator ownership.</p></article>
        <article><h3>Buyback funding is visible; execution remains unverified</h3><p>Since {{ buybackRows[0]?.date ?? '—' }}, the tracked series records funding attributed to NEAR Intents and 1Click &amp; other revenue. <a href="https://revenue.near.org/" target="_blank" rel="noopener noreferrer">NEAR Revenue</a> identifies captured revenue as funding for buybacks. As of {{ tokenomics?.metrics?.buyback_wallet_balance_date ?? '—' }}, the designated wallet holds {{ formatCompact(tokenomics?.metrics?.buyback_wallet_balance_near, 2) }} NEAR in liquid balance. Historical records show recurring Intents inflows and more episodic 1Click flows, including 502,793 NEAR recorded on September 9, 2026. These observations establish visible funding flows and the wallet’s current balance, but do not independently verify completed purchases or the subsequent custody of acquired tokens.</p></article>
      </div>
      <div class="research-link-row"><NuxtLink to="/intents">Inspect Intents evidence <ArrowRight :size="13" /></NuxtLink><NuxtLink to="/tokenomics">Inspect supply and staking <ArrowRight :size="13" /></NuxtLink><NuxtLink to="/protocols">Inspect protocol revenue <ArrowRight :size="13" /></NuxtLink></div>
      </div>
    </section>

    <section id="implications" class="research-section">
      <div class="research-section-heading"><span class="research-icon"><Scale :size="18" /></span><div><p class="eyebrow">05 · INTERPRETATION</p><h2>Investment implications</h2></div></div>
      <div class="panel-card research-section-content">
      <div class="research-implications-grid">
        <div><h3>What supports the case</h3><ul><li>The network has multi-year activity history, and NEAR Intents reports {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_all_time, 'USD', 1) }} in all-time volume and {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_1y, 'USD', 1) }} over the trailing year.</li><li>Transactions are up {{ fmtPct(network?.key_metrics?.transactions?.change_30d_pct) }} and active accounts are up {{ fmtPct(network?.key_metrics?.active_accounts?.change_30d_pct) }} over the latest 30-day network comparison; stablecoin supply is also higher.</li><li>NEAR Intents reports {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1) }} in 30-day volume, alongside fee, revenue, and holders-revenue series that make reported value allocation measurable.</li><li>{{ formatCompact(tokenomics?.metrics?.total_active_stake, 0) }} NEAR is reported staked across {{ formatCompact(tokenomics?.metrics?.active_validators_count, 0) }} active validators; the top validator’s reported share is {{ fmtPct(tokenomics?.metrics?.top_1_stake_share) }}.</li></ul></div>
        <div><h3>What remains unproven</h3><ul><li>Network TVL and NEAR Intents TVL are down {{ fmtPct(network?.key_metrics?.tvl_usd?.change_30d_pct) }} and {{ fmtPct(intents?.key_metrics?.tvl_usd?.change_30d_pct) }} respectively; the latest 30-day Intents volume, fees, and revenue comparisons are also lower. These are short-term changes and are not attributed to NEAR-specific causes; broad market effects are not isolated in this dataset.</li><li>Net supply increased by {{ formatCompact(tokenomics?.metrics?.net_supply_change_30d_near, 2) }} NEAR through {{ tokenomics?.data_quality?.daily_supply?.latest_date ?? '—' }}. Separately, in the latest complete 30-day flow window through {{ tokenomics?.metrics?.latest_burn_coverage_date ?? '—' }}, net fee burn offset {{ fmtPct(tokenomics?.metrics?.burn_offset_30d_pct) }} of estimated gross issuance.</li><li>The {{ fmtPct(intents?.key_metrics?.revenue_capture_rate_30d_pct?.value) }} Intents revenue-capture rate is provider-based and timing-sensitive; it is not a direct yield to NEAR holders. Wallet inflows are not verified purchases.</li><li>Supply precision is approximate, current stake and supply dates can differ, and incomplete validator metadata prevents some concentration and performance aggregates.</li></ul></div>
      </div>
      <p class="research-conclusion"><strong>Assessment:</strong> the longer record supports genuine ecosystem scale: network activity has a multi-year history, and Intents reports {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_all_time, 'USD', 1) }} in total volume, including {{ formatCurrency(intents?.key_metrics?.volume_usd?.total_1y, 'USD', 1) }} over the trailing year. That establishes substantial activity, but volume is not revenue. The value-capture evidence is less conclusive: in the latest reported 30-day window, Intents revenue and network TVL were lower than in the prior window. Total supply rose {{ formatCompact(tokenomics?.metrics?.net_supply_change_30d_near, 2) }} NEAR through {{ tokenomics?.data_quality?.daily_supply?.latest_date ?? '—' }}; in the separate complete flow window through {{ tokenomics?.metrics?.latest_burn_coverage_date ?? '—' }}, fee burn offset {{ fmtPct(tokenomics?.metrics?.burn_offset_30d_pct) }} of estimated gross issuance. These short-term movements do not establish a long-term decline and are not attributed here to NEAR-specific causes. Staking supports network participation, but available concentration data cannot establish independent validator control or holder returns. Taken together, the data support a case for sustained network use and substantial Intents activity. They do not yet show that this activity reliably becomes durable value for NEAR holders.</p>
      </div>
    </section>

    <section id="reproducibility" class="research-section">
      <div class="research-section-heading"><span class="research-icon"><Database :size="18" /></span><div><p class="eyebrow">06 · DATA &amp; REPRODUCIBILITY</p><h2>Sources, ranges, and refresh process</h2></div></div>
      <div class="panel-card research-section-content">
      <div class="research-source-grid">
        <div><h3>Where the data come from</h3><ul><li><strong>NearBlocks:</strong> network stats and current validator data; fetched incrementally where the source supports historical dates.</li><li><strong>DefiLlama:</strong> stablecoin supply, NEAR Intents volume/TVL/revenue/fees, broader NEAR revenue breakdown, and DEX volume.</li><li><strong>Google BigQuery public NEAR mainnet:</strong> daily supply snapshots, execution-outcome <code>tokens_burnt</code>, contract-reward event audit, and buyback transfer records.</li><li><strong>Binance:</strong> daily NEARUSDT closes used as the project’s USD price proxy.</li><li><strong>FastNEAR archival RPC:</strong> historical active validator stake and finalized buyback wallet balance.</li></ul></div>
        <div><h3>How to reproduce the figures</h3><ul><li>Raw provider responses are under <code>data/raw/</code>; parser outputs are under <code>data/normalized/</code>; dashboard-ready datasets are under <code>data/analytics/</code>.</li><li>Dataset-specific definitions and data coverage are maintained in <code>docs/analytics/</code>, especially <code>tokenomics.md</code> and <code>network.md</code>.</li><li>Run <code>py scripts/main.py</code> from the repository root to fetch, normalize, and build analytics. The historical validator-stake collector runs last because it uses block heights in raw BigQuery <code>daily_supply.json</code>.</li><li>Run <code>py scripts/build_analytics.py</code> to rebuild Analytics from existing normalized files without fetching. It syncs the new Analytics files to the dashboard at the end. From <code>dashboard/</code>, <code>npm run sync:data</code> remains available for a manual sync.</li><li>Daily sources use successful-request cooldowns and resume from their latest raw dates; the current UTC day is not queried as a completed daily observation. Failed sources remain eligible for retry. See the README for credentials, local setup, and provider details.</li></ul></div>
      </div>
      <p class="research-source">Data snapshot last updated {{ updated ?? '—' }}. Values may carry source-specific timestamps and precision. Use the timestamp attached to each metric and the data-quality metadata before comparing periods.</p>
      </div>
    </section>
  </template>
</template>
