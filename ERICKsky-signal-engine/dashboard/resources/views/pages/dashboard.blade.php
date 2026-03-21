@extends('layouts.app')
@section('title', 'Dashboard — ERICKsky Signal Engine')

@section('content')
<div class="space-y-6">

    {{-- Page Header --}}
    <div class="flex items-center justify-between">
        <h1 class="text-2xl font-bold">Dashboard</h1>
        <div class="flex gap-2 items-center">
            <span class="badge badge-success gap-1">
                <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                Bot Active
            </span>
            <span class="text-xs opacity-50" id="last-updated">—</span>
        </div>
    </div>

    {{-- Live Performance Stats (Livewire) --}}
    @livewire('performance-stats')

    {{-- Institutional Filter Effectiveness --}}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">

        {{-- Regime Win Rates --}}
        <div class="card bg-base-200 shadow-xl col-span-1">
            <div class="card-body p-4">
                <h2 class="card-title text-sm">🌊 Regime Win Rates</h2>
                <div id="regime-stats" class="space-y-2 text-sm">
                    @foreach(['TRENDING' => ['badge-success','🚀'], 'RANGING' => ['badge-warning','📊'], 'VOLATILE' => ['badge-error','💥']] as $regime => [$badge, $emoji])
                    <div class="flex items-center justify-between">
                        <span>{{ $emoji }} {{ $regime }}</span>
                        @php
                            $r = $regimeStats[$regime] ?? null;
                            $winRate = $r ? ($r['wins'] + ($r['total']-$r['wins']) > 0 ? round($r['wins']/$r['total']*100,1) : 0) : 0;
                        @endphp
                        <span class="badge {{ $badge }} badge-sm">{{ $winRate }}%</span>
                    </div>
                    @endforeach
                </div>
            </div>
        </div>

        {{-- Filter Effectiveness --}}
        <div class="card bg-base-200 shadow-xl col-span-1">
            <div class="card-body p-4">
                <h2 class="card-title text-sm">🔍 Filter Effectiveness (30d)</h2>
                <div class="space-y-2">
                    <div class="flex justify-between text-sm">
                        <span>Avg Consensus Score</span>
                        <span class="font-mono font-bold text-info">{{ $filterStats['avg_score'] }}/100</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span>Avg M15 Score</span>
                        <span class="font-mono font-bold text-success">{{ $filterStats['avg_m15_score'] }}/100</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span>M15 Confirm Rate</span>
                        <span class="font-mono font-bold">{{ $filterStats['m15_confirm_rate'] }}%</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span>Pattern Signal Rate</span>
                        <span class="font-mono font-bold">{{ $filterStats['pattern_signal_rate'] }}%</span>
                    </div>
                </div>
            </div>
        </div>

        {{-- Upcoming News --}}
        <div class="card bg-base-200 shadow-xl col-span-1">
            <div class="card-body p-4">
                <h2 class="card-title text-sm">📰 Upcoming News (8h)</h2>
                <div id="news-events" class="space-y-1 text-xs">
                    <span class="opacity-50 italic">Loading...</span>
                </div>
            </div>
        </div>
    </div>

    {{-- TradingView Charts --}}
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        @foreach(['EURUSD', 'GBPUSD', 'XAUUSD', 'AUDUSD'] as $pair)
        <div class="card bg-base-200 shadow-xl">
            <div class="card-body p-3">
                <h3 class="card-title text-sm font-bold">{{ $pair }}</h3>
                <div class="tradingview-widget-container" style="height:160px">
                    <div class="tradingview-widget-container__widget"></div>
                    <script type="text/javascript">
                    (function() {
                        var symbol = "{{ $pair }}" === "XAUUSD" ? "OANDA:XAUUSD" : "FX:{{ $pair }}";
                        var script = document.createElement('script');
                        script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js';
                        script.async = true;
                        script.innerHTML = JSON.stringify({
                            "symbol": symbol, "width": "100%", "height": 160,
                            "locale": "en", "dateRange": "1D", "colorTheme": "dark",
                            "isTransparent": true, "autosize": false
                        });
                        document.currentScript.parentElement.appendChild(script);
                    })();
                    </script>
                </div>
            </div>
        </div>
        @endforeach
    </div>

    {{-- Live Signal Feed --}}
    <div class="card bg-base-200 shadow-xl">
        <div class="card-body">
            <h2 class="card-title text-lg">
                <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                Live Signal Feed
                <span class="text-xs text-base-content/50 font-normal">(refreshes every 10s)</span>
            </h2>
            @livewire('live-signal-feed')
        </div>
    </div>

</div>
@endsection

@push('scripts')
<script>
// ── Fetch upcoming news events from local API ─────────────────────────────
async function loadNewsEvents() {
    try {
        const res  = await fetch('/api/news-events?hours=8');
        const data = await res.json();
        const el   = document.getElementById('news-events');
        if (!data.events.length) {
            el.innerHTML = '<span class="opacity-50 italic">No high-impact news in next 8h ✅</span>';
            return;
        }
        el.innerHTML = data.events.map(e => {
            const time = new Date(e.event_time).toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit'});
            const impact = e.impact === 'HIGH' ? '🔴' : '🟡';
            return `<div class="flex gap-1 items-center">
                ${impact} <span class="font-mono text-warning">${time}</span>
                <span class="font-bold">${e.currency}</span>
                <span class="opacity-70 truncate">${e.title}</span>
            </div>`;
        }).join('');
    } catch(e) {
        document.getElementById('news-events').innerHTML =
            '<span class="opacity-40 italic">News DB not yet populated</span>';
    }
}

// ── Live stats ticker ─────────────────────────────────────────────────────
async function refreshStats() {
    try {
        const res  = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('last-updated').textContent =
            'Updated: ' + new Date().toLocaleTimeString();
    } catch(e) {}
}

loadNewsEvents();
refreshStats();
setInterval(refreshStats, 10000);
setInterval(loadNewsEvents, 60000);
</script>
@endpush
