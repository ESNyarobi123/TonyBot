@props(['signal'])

<div class="card bg-base-300 shadow border border-base-100/10 hover:border-primary/20 transition-all">
    <div class="card-body p-4">

        {{-- Header --}}
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                    {{ $signal->direction === 'BUY' ? 'bg-success/20 text-success' : 'bg-error/20 text-error' }}">
                    {{ $signal->direction === 'BUY' ? '▲' : '▼' }}
                </div>
                <div>
                    <span class="font-bold">{{ $signal->pair }}</span>
                    <span class="badge badge-sm {{ $signal->direction_badge }} ml-1">{{ $signal->direction }}</span>
                </div>
            </div>
            <div class="text-right">
                <span class="badge badge-sm {{ $signal->status_badge }}">{{ $signal->status }}</span>
                <div class="text-xs text-base-content/50 mt-1">{{ $signal->created_at?->diffForHumans() }}</div>
            </div>
        </div>

        {{-- Price levels --}}
        <div class="grid grid-cols-3 gap-2 mt-3 text-sm">
            <div class="bg-base-200 rounded p-2 text-center">
                <div class="text-xs text-base-content/50">Entry</div>
                <div class="font-mono font-semibold text-xs">{{ number_format($signal->entry_price, 5) }}</div>
            </div>
            <div class="bg-base-200 rounded p-2 text-center">
                <div class="text-xs text-error">Stop Loss</div>
                <div class="font-mono text-error text-xs">{{ number_format($signal->stop_loss, 5) }}</div>
            </div>
            <div class="bg-base-200 rounded p-2 text-center">
                <div class="text-xs text-success">TP1</div>
                <div class="font-mono text-success text-xs">{{ number_format($signal->take_profit_1, 5) }}</div>
            </div>
        </div>

        {{-- Footer --}}
        <div class="flex items-center justify-between mt-3 pt-2 border-t border-base-100/10 text-xs text-base-content/50">
            <span>{{ strtoupper($signal->timeframe) }} • R:R {{ $signal->risk_reward }}</span>
            <div class="flex items-center gap-2">
                <span class="badge badge-sm {{ $signal->confidence_badge }}">{{ str_replace('_',' ',$signal->confidence) }}</span>
                <span class="font-mono">{{ $signal->consensus_score }}/100</span>
            </div>
        </div>

    </div>
</div>
