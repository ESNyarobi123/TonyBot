<div class="space-y-4">

    {{-- Pair + Timeframe Tabs --}}
    <div class="flex flex-wrap gap-3 items-center">
        <div class="tabs tabs-boxed bg-base-300">
            @foreach($pairs as $p)
            <button wire:click="setPair('{{ $p }}')"
                    class="tab tab-sm {{ $pair === $p ? 'tab-active' : '' }}">
                {{ $p }}
            </button>
            @endforeach
        </div>

        <div class="tabs tabs-boxed bg-base-300 ml-auto">
            @foreach($timeframes as $tf => $label)
            <button wire:click="setTimeframe('{{ $tf }}')"
                    class="tab tab-sm {{ $timeframe === $tf ? 'tab-active' : '' }}">
                {{ $label }}
            </button>
            @endforeach
        </div>
    </div>

    {{-- TradingView Chart --}}
    <div class="card bg-base-300 shadow overflow-hidden" style="height: 420px">
        <div wire:ignore id="tv-chart-container-{{ $pair }}" style="height: 100%">
            <div class="tradingview-widget-container" style="height: 100%; width: 100%">
                <div class="tradingview-widget-container__widget" style="height: calc(100% - 32px); width: 100%"></div>
                <div class="tradingview-widget-copyright">
                    <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">
                        <span class="text-xs text-base-content/30">TradingView</span>
                    </a>
                </div>
                <script type="text/javascript"
                    src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
                    async>
                {
                    "autosize": true,
                    "symbol": "{{ $tvSymbol }}",
                    "interval": "{{ $tvInterval }}",
                    "timezone": "UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "enable_publishing": false,
                    "hide_top_toolbar": false,
                    "hide_legend": false,
                    "save_image": false,
                    "calendar": false,
                    "hide_volume": false,
                    "support_host": "https://www.tradingview.com"
                }
                </script>
            </div>
        </div>
    </div>

    {{-- Recent Signals for This Pair --}}
    @if($recentSignals->isNotEmpty())
    <div>
        <h4 class="text-sm font-semibold text-base-content/70 mb-2">Recent {{ $pair }} Signals</h4>
        <div class="flex gap-2 flex-wrap">
            @foreach($recentSignals as $sig)
            <div class="badge badge-outline gap-1
                {{ $sig->direction === 'BUY' ? 'badge-success' : 'badge-error' }}">
                {{ $sig->direction }}
                <span class="font-mono text-xs">{{ number_format($sig->entry_price, 5) }}</span>
                <span class="badge badge-sm {{ $sig->status_badge }}">{{ $sig->status }}</span>
            </div>
            @endforeach
        </div>
    </div>
    @endif

</div>
