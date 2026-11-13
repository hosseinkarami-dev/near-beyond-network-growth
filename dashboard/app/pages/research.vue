<script setup lang="ts">
import { ArrowRight, BookOpenCheck, Database, Scale, TrendingUp } from '@lucide/vue'
import { fetchAnalyticsOrEmpty, formatCompact, formatCurrency, formatPercent } from '~/composables/useAnalytics'
import { onBeforeUnmount, onMounted, ref } from 'vue'

const analyticsBaseUrl = useRuntimeConfig().public.analyticsBaseUrl as string
const paths = ['dashboard.json', 'tokenomics/snapshot.json', 'near_intents/snapshot.json', 'protocols/revenue/snapshot.json']
const { data, pending, error, refresh } = await useAsyncData('research-methodology-data', async () => {
  const documents = await Promise.all(paths.map((path) => fetchAnalyticsOrEmpty(path, analyticsBaseUrl)))
  return Object.fromEntries(paths.map((path, index) => [path, documents[index]]))
}, { server: false })
const doc = (path: string) => data.value?.[path]
const tokenomics = computed(() => doc('tokenomics/snapshot.json'))
const intents = computed(() => doc('near_intents/snapshot.json'))
const protocolRevenue = computed(() => doc('protocols/revenue/snapshot.json')?.summary)
const methods = computed(() => doc('dashboard.json')?.methodologies)
const updated = computed(() => doc('dashboard.json')?.latest_data_update)
const fmtPct = (value: unknown) => value == null ? '—' : formatPercent(value as number | string)
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
    <PageHeading eyebrow="RESEARCH &amp; METHODOLOGY" title="Beyond Network Growth" description="Is NEAR Turning Ecosystem Growth into Sustainable Economic Value?" :updated-at="updated" />

    <nav class="research-toc" aria-label="Research page sections">
      <a v-for="section in researchSections" :key="section.id" :href="`#${section.id}`" :class="{ active: activeSection === section.id }" :aria-current="activeSection === section.id ? 'location' : undefined" @click.prevent="scrollToSection(section.id)">{{ section.label }}</a>
    </nav>

    <section id="thesis" class="research-section panel-card">
      <div class="research-section-heading"><span class="research-icon"><BookOpenCheck :size="18" /></span><div><p class="eyebrow">01 · INVESTMENT THESIS</p><h2>Research question</h2></div></div>
      <p class="research-lead">Is growth in NEAR’s network and ecosystem producing durable economic value that reaches the protocol and NEAR holders, while remaining sustainable as token supply expands?</p>
      <p>More transactions, liquidity, and cross-chain flows can indicate adoption without necessarily creating material fees, retained revenue, or token-holder value. This research follows the evidence from network activity through protocol economics and value capture, then compares it with supply expansion and staking participation. The dashboard reports these as separate measures because they have different units, attribution rules, and data coverage.</p>
      <div class="research-callout"><strong>Interpretation rule</strong><span>Activity is evidence of usage. Revenue and holder allocation are evidence of reported value capture. Wallet transfers are evidence of fund flows. None alone establishes sustainable value accrual or confirms a token purchase.</span></div>
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
      <p class="research-intro">The dashboard’s analytics layer computes derived measures and period aggregates. The web application formats and displays the published analytics outputs; it does not calculate the metrics below.</p>
      <div class="research-method-grid">
        <article class="panel-card research-method"><h3>Supply expansion and issuance</h3><p><strong>Net issuance (daily)</strong> is the change between consecutive total-supply snapshots: <code>Total supply(D) − Total supply(D−1)</code>.</p><p><strong>Net fee burn</strong> is <code>execution_outcomes.tokens_burnt − contract rewards</code>. The query’s <code>tokens_burnt</code> amount is used as reported; it is not reconstructed from gas burnt times gas price.</p><p><strong>Estimated gross issuance</strong> is <code>net issuance + net fee burn</code>. It is an estimate, not a direct validator reward observation.</p><p><strong>Annualized net inflation · 30D</strong> is compounded from total supply at D and D−30: <code>((supply(D) / supply(D−30))^(365/30) − 1) × 100</code>. It includes the effect of burns through the net total-supply change.</p><p><strong>Burn coverage</strong> compares net fee burn with estimated gross issuance: <code>sum(net fee burn) / sum(estimated gross issuance) × 100</code> for the selected period. It is undefined where the denominator is zero or negative.</p><p class="research-source">Sources: BigQuery public NEAR mainnet <code>daily_supply</code>, <code>daily_gross_burn</code>, and the fixed-range <code>contract_reward_event_audit</code>. Supply values use approximate FLOAT64 precision; gross issuance is affected by missing inputs and unmodeled supply adjustments.</p><MethodologyTip v-if="methods?.tokenomics?.supply_dynamics" :items="[methods.tokenomics.supply_dynamics, methods.tokenomics.net_burn, methods.tokenomics.net_inflation, methods.tokenomics.burn_coverage]" /></article>

        <article class="panel-card research-method"><h3>NEAR Intents value capture</h3><p><strong>30-day revenue capture rate</strong> is <code>(sum of daily NEAR Intents revenue over trailing 30 days ÷ sum of gross fees over the same dates) × 100</code>. It uses the ratio of sums, not the average of daily ratios; it is not capped at 100%.</p><p>Revenue and gross fees are separate provider series and need not reconcile each day. Periodic wallet sweeps can cause revenue to be recognized later than the fees that generated it, so short-window rates can be timing-sensitive. Holders revenue is a separate allocation series and is not added a second time to revenue.</p><p>Protocol revenue is shown beside NEAR Intents revenue for context. NEAR Intents is also a protocol entry in the broader protocols dataset, so these series must not be added together as independent revenue.</p><p class="research-source">Sources: DefiLlama normalized NEAR Intents volume, fees, revenue, and holder-revenue datasets; protocol revenue breakdown.</p><MethodologyTip v-if="methods?.near_intents?.revenue_capture_rate_30d" :items="[methods.near_intents.volume, methods.near_intents.gross_fees, methods.near_intents.revenue, methods.near_intents.revenue_capture_rate_30d].filter(Boolean)" /></article>

        <article class="panel-card research-method"><h3>Staking and validator security</h3><p><strong>Staking ratio</strong> is current active validator stake divided by latest circulating supply, multiplied by 100. The supply denominator is an approximate FLOAT64 observation.</p><p><strong>Top 10 stake share</strong> is the combined stake of the ten largest active validators divided by total active validator stake. It measures concentration within active stake, not the share of circulating supply.</p><p>Historical daily stake uses each daily-supply block height, resolves its epoch through FastNEAR RPC, sums current validator stakes using arbitrary-precision integers, then converts YoctoNEAR to NEAR. Calendar-period series select the last observed daily snapshot; they are not cumulative.</p><p class="research-source">Sources: NearBlocks current validator endpoints, BigQuery daily supply, and FastNEAR archival RPC. Delegator totals may double-count accounts delegating to multiple validators.</p><MethodologyTip v-if="methods?.tokenomics?.staking" :items="[methods.tokenomics.staking, methods.tokenomics.validators, methods.tokenomics.historical_active_stake]" /></article>

        <article class="panel-card research-method"><h3>Buyback-related fund flows</h3><p>The transfer chart combines native NEAR transfers and wNEAR <code>ft_transfer</code> events into one NEAR-denominated inflow per attributed source for <code>buybacks.multisignature.near</code>. The wallet balance is the liquid amount returned by a finalized FastNEAR RPC account view.</p><p>Wallet inflows are not confirmation that an open-market purchase occurred. They do not establish execution price, amount purchased, custody changes, or a burn. Balance and historical inflow totals have different time coverage and must not be reconciled as if they were the same flow.</p><p class="research-source">Source: BigQuery buyback transfer query from 2026-04-01 onward; FastNEAR finalized RPC wallet balance.</p><MethodologyTip v-if="methods?.tokenomics?.buybacks" :items="methods.tokenomics.buybacks" /></article>
      </div>
    </section>

    <section id="findings" class="research-section">
      <div class="research-section-heading"><span class="research-icon"><TrendingUp :size="18" /></span><div><p class="eyebrow">04 · OBSERVED EVIDENCE</p><h2>Key findings</h2></div></div>
      <p class="research-intro">Values below are taken directly from the generated analytics snapshots. Their source dates differ by metric; each date is shown to avoid implying a single synchronized observation.</p>
      <div class="metric-grid dashboard-metrics dashboard-metrics-three research-findings-grid">
        <MetricCard label="NEAR Intents volume · 30D" :value="formatCurrency(intents?.key_metrics?.volume_usd?.total_30d, 'USD', 1)" :detail="`Through ${intents?.key_metrics?.volume_usd?.date ?? '—'}`" :change-label="''" />
        <MetricCard label="NEAR Intents revenue capture · 30D" :value="fmtPct(intents?.key_metrics?.revenue_capture_rate_30d_pct?.value)" :detail="`As of ${intents?.key_metrics?.revenue_capture_rate_30d_pct?.date ?? '—'}`" :change-label="''" />
        <MetricCard label="NEAR Intents revenue · 30D" :value="formatCurrency(intents?.key_metrics?.revenue_usd?.total_30d, 'USD', 0)" :detail="`Through ${intents?.key_metrics?.revenue_usd?.date ?? '—'}`" :change-label="''" />
        <MetricCard label="Protocol revenue · 30D" :value="formatCurrency(protocolRevenue?.total_30d, 'USD', 0)" :detail="`Snapshot ${doc('protocols/revenue/snapshot.json')?.updated_at?.slice(0, 10) ?? '—'}`" :change-label="''" />
        <MetricCard label="Annualized net inflation · 30D" :value="fmtPct(tokenomics?.metrics?.net_inflation_30d_annualized_pct)" :detail="`Supply through ${tokenomics?.data_quality?.daily_supply?.latest_date ?? '—'}`" :change-label="''" />
        <MetricCard label="Estimated gross issuance · 30D" :value="`${formatCompact(tokenomics?.metrics?.gross_issuance_30d_near, 2)} NEAR`" :detail="`Net fee burn ${formatCompact(tokenomics?.metrics?.net_burn_30d_near, 2)} NEAR · last 30D`" :change-label="''" />
        <MetricCard label="Burn coverage · 30D" :value="fmtPct(tokenomics?.metrics?.burn_offset_30d_pct)" :detail="`As of ${tokenomics?.data_quality?.daily_gross_burn?.latest_date ?? '—'}`" :change-label="''" />
        <MetricCard label="Staking ratio" :value="fmtPct(tokenomics?.metrics?.staking_ratio)" :detail="`${formatCompact(tokenomics?.metrics?.total_active_stake, 1)} NEAR active stake`" :change-label="''" />
        <MetricCard label="Top 10 stake share" :value="fmtPct(tokenomics?.metrics?.top_10_stake_share)" :detail="`${formatCompact(tokenomics?.metrics?.active_validators_count, 0)} active validators`" :change-label="''" />
      </div>
      <ul class="research-findings-notes">
        <li>Observed ecosystem activity is material in the reported Intents volume series, while the reported 30-day revenue capture rate is lower than 100%; revenue-recognition timing and provider series definitions limit direct day-by-day interpretation.</li>
        <li>Estimated gross issuance substantially exceeds net fee burn in the current 30-day analytics window. This is a supply accounting comparison, not a forecast of future issuance.</li>
        <li>Active stake is a large share of circulating supply, while the Top 10 share indicates that active stake is distributed across more than a handful of validators. Stake concentration alone does not establish validator independence or operational resilience.</li>
      </ul>
      <div class="research-link-row"><NuxtLink to="/intents">Inspect Intents evidence <ArrowRight :size="13" /></NuxtLink><NuxtLink to="/tokenomics">Inspect supply and staking <ArrowRight :size="13" /></NuxtLink><NuxtLink to="/protocols">Inspect protocol revenue <ArrowRight :size="13" /></NuxtLink></div>
    </section>

    <section id="implications" class="research-section panel-card">
      <div class="research-section-heading"><span class="research-icon"><Scale :size="18" /></span><div><p class="eyebrow">05 · INTERPRETATION</p><h2>Investment implications</h2></div></div>
      <div class="research-implications-grid">
        <div><h3>Evidence supporting the thesis</h3><ul><li>NEAR Intents records substantial cross-chain swap volume and provider-reported revenue.</li><li>The analytics expose a measurable holder-revenue allocation and a 30-day capture-rate series.</li><li>Active validator stake and historical stake observations provide evidence to assess participation and security alongside economics.</li></ul></div>
        <div><h3>Evidence that tempers it</h3><ul><li>Reported revenue capture is sensitive to wallet-sweep timing and comes from provider-classified data.</li><li>Net fee burn offsets only part of estimated gross issuance in the current measured period; the estimate relies on approximate supply snapshots.</li><li>Observed buyback wallet inflows do not prove completed purchases, and reported activity does not by itself establish durable holder value.</li></ul></div>
      </div>
      <p class="research-conclusion">Taken together, the current evidence supports ecosystem activity and some reported value capture, while showing that supply expansion remains a separate and material consideration. The dataset does not establish that growth will persist or that reported fund flows translate into realized value for holders. This is an evidence summary, not a directional price recommendation.</p>
    </section>

    <section id="reproducibility" class="research-section panel-card">
      <div class="research-section-heading"><span class="research-icon"><Database :size="18" /></span><div><p class="eyebrow">06 · DATA &amp; REPRODUCIBILITY</p><h2>Sources, ranges, and refresh process</h2></div></div>
      <div class="research-source-grid">
        <div><h3>Provider datasets</h3><ul><li><strong>NearBlocks:</strong> network stats and current validator data; fetched incrementally where the source supports historical dates.</li><li><strong>DefiLlama:</strong> stablecoin supply, NEAR Intents volume/TVL/revenue/fees, and protocol revenue and DEX volume.</li><li><strong>Google BigQuery public NEAR mainnet:</strong> daily supply snapshots, execution-outcome <code>tokens_burnt</code>, contract-reward event audit, and buyback transfer records.</li><li><strong>Binance:</strong> daily NEARUSDT closes used as the project’s USD price proxy.</li><li><strong>FastNEAR archival RPC:</strong> historical active validator stake and finalized buyback wallet balance.</li></ul></div>
        <div><h3>Project resources and update cadence</h3><ul><li>Raw provider responses are under <code>data/raw/</code>; parser outputs are under <code>data/normalized/</code>; dashboard-ready datasets are under <code>data/analytics/</code>.</li><li>Dataset-specific definitions and data coverage are maintained in <code>docs/analytics/</code>, including <code>tokenomics.md</code> and <code>near_intents.md</code>.</li><li>Run <code>python scripts/main.py</code> from the repository root to fetch, normalize, and build analytics. The validator stake collector runs last so it can use the latest daily-supply block references.</li><li>Run <code>python scripts/build_analytics.py</code> to rebuild analytics from local normalized files without fetching; from <code>dashboard/</code>, <code>npm run sync:data</code> refreshes the data served by an existing dev server.</li></ul></div>
      </div>
      <p class="research-source">Coverage is not uniform: supply snapshots extend from {{ tokenomics?.data_quality?.daily_supply?.start_date }} through {{ tokenomics?.data_quality?.daily_supply?.latest_date }}; exact historical validator stake starts {{ tokenomics?.data_quality?.daily_active_validator_stake?.start_date }}; the audited contract-reward series covers 2026-01-01 through 2026-11-04, followed by protocol-version-defined zeros from 2026-11-05. Missing or unavailable source data remains blank unless the analytics policy explicitly defines a zero.</p>
      <p class="research-source">Data snapshot last updated {{ updated ?? '—' }}. Values may carry source-specific timestamps and precision. Use the timestamp attached to each metric and the data-quality metadata before comparing periods.</p>
    </section>
  </template>
</template>
