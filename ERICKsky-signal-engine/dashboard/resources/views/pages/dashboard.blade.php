@extends('layouts.app')
@section('title', 'Dashboard — ERICKsky Signal Engine')

@section('content')
<div class="space-y-6">

    {{-- Page Header --}}
    <div class="flex items-center justify-between">
        <h1 class="text-2xl font-bold">Dashboard</h1>
        <div class="flex gap-2">
            <span class="badge badge-success gap-1">
                <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                Bot Active
            </span>
        </div>
    </div>

    {{-- Live Performance Stats (Livewire) --}}
    @livewire('performance-stats')

    {{-- TradingView Charts Grid --}}
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
                            "symbol": symbol,
                            "width": "100%",
                            "height": 160,
                            "locale": "en",
                            "dateRange": "1D",
                            "colorTheme": "dark",
                            "isTransparent": true,
                            "autosize": false,
                            "largeChartUrl": ""
                        });
                        document.currentScript.parentElement.appendChild(script);
                    })();
                    </script>
                </div>
            </div>
        </div>
        @endforeach
    </div>

    {{-- Live Signal Feed (Livewire) --}}
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
