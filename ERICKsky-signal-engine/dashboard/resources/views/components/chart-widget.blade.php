@props(['symbol' => 'EURUSD', 'height' => '200'])

<div class="tradingview-widget-container" style="height: {{ $height }}px; width: 100%">
    <div class="tradingview-widget-container__widget" style="height: 100%; width: 100%"></div>
    <script type="text/javascript"
        src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js"
        async>
    {
        "symbol": "FX:{{ $symbol }}",
        "width": "100%",
        "height": {{ $height }},
        "locale": "en",
        "dateRange": "1D",
        "colorTheme": "dark",
        "isTransparent": true,
        "autosize": false
    }
    </script>
</div>
