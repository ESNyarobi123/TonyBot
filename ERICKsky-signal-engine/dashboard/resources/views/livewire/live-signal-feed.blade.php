<div class="space-y-4">

    {{-- Filters --}}
    <div class="flex flex-wrap gap-3 items-center">
        <select wire:model.live="filterPair" class="select select-bordered select-sm w-32">
            <option value="">All Pairs</option>
            @foreach($pairs as $pair)
                <option value="{{ $pair }}">{{ $pair }}</option>
            @endforeach
        </select>
        <select wire:model.live="filterDirection" class="select select-bordered select-sm w-28">
            <option value="">All</option>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
        </select>
        <div class="ml-auto text-xs text-base-content/50 flex items-center gap-1">
            <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
            Live — {{ $signals->count() }} signals
        </div>
    </div>

    {{-- Signal Cards --}}
    <div class="space-y-3">
        @forelse($signals as $signal)
        <div class="card bg-base-300 shadow border border-base-100/10 hover:border-primary/30 transition-all">
            <div class="card-body p-4">
                <div class="flex items-start justify-between gap-4 flex-wrap">

                    {{-- Left: Pair + Direction --}}
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm
                            {{ $signal->direction === 'BUY' ? 'bg-success/20 text-success' : 'bg-error/20 text-error' }}">
                            {{ $signal->direction === 'BUY' ? '▲' : '▼' }}
                        </div>
                        <div>
                            <div class="font-bold text-base">{{ $signal->pair }}</div>
                            <span class="badge badge-sm {{ $signal->direction_badge }}">{{ $signal->direction }}</span>
                        </div>
                    </div>

                    {{-- Center: Prices --}}
                    <div class="grid grid-cols-3 gap-4 text-sm">
                        <div>
                            <div class="text-xs text-base-content/50">Entry</div>
                            <div class="font-mono font-semibold">{{ number_format($signal->entry_price, 5) }}</div>
                        </div>
                        <div>
                            <div class="text-xs text-error">Stop Loss</div>
                            <div class="font-mono text-error">{{ number_format($signal->stop_loss, 5) }}</div>
                        </div>
                        <div>
                            <div class="text-xs text-success">TP1</div>
                            <div class="font-mono text-success">{{ number_format($signal->take_profit_1, 5) }}</div>
                        </div>
                    </div>

                    {{-- Right: Score + Status --}}
                    <div class="flex items-center gap-3">
                        <div class="radial-progress text-primary text-xs font-bold"
                             style="--value:{{ $signal->consensus_score }}; --size:3rem; --thickness:3px">
                            {{ $signal->consensus_score }}
                        </div>
                        <div class="text-right">
                            <span class="badge badge-sm {{ $signal->confidence_badge }} block mb-1">
                                {{ str_replace('_', ' ', $signal->confidence) }}
                            </span>
                            <span class="badge badge-sm {{ $signal->status_badge }}">
                                {{ $signal->status }}
                            </span>
                        </div>
                    </div>
                </div>

                {{-- Footer --}}
                <div class="flex items-center justify-between mt-2 pt-2 border-t border-base-100/10">
                    <div class="flex gap-2">
                        @if($signal->take_profit_2)
                        <span class="text-xs text-success">TP2: {{ number_format($signal->take_profit_2, 5) }}</span>
                        @endif
                        @if($signal->take_profit_3)
                        <span class="text-xs text-success">TP3: {{ number_format($signal->take_profit_3, 5) }}</span>
                        @endif
                    </div>
                    <div class="flex items-center gap-3 text-xs text-base-content/50">
                        <span>{{ strtoupper($signal->timeframe) }}</span>
                        <span>R:R {{ $signal->risk_reward }}</span>
                        <span>{{ $signal->created_at?->diffForHumans() }}</span>
                    </div>
                </div>
            </div>
        </div>
        @empty
        <div class="text-center py-12 text-base-content/40">
            <div class="text-4xl mb-3">📡</div>
            <div class="text-lg">No signals yet</div>
            <div class="text-sm mt-1">The bot will generate signals during active trading sessions.</div>
        </div>
        @endforelse
    </div>

    {{-- Load More --}}
    @if($signals->count() >= $limit)
    <div class="text-center">
        <button wire:click="loadMore" class="btn btn-ghost btn-sm">
            Load More
            <span wire:loading wire:target="loadMore" class="loading loading-spinner loading-xs"></span>
        </button>
    </div>
    @endif
</div>
