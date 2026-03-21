@extends('layouts.app')
@section('title', 'Signals — ERICKsky Signal Engine')

@section('content')
<div class="space-y-4">

    {{-- Header --}}
    <div class="flex items-center justify-between">
        <h1 class="text-2xl font-bold">Signals</h1>
        <a href="{{ route('signals.export') }}" class="btn btn-sm btn-outline gap-1">
            ⬇ Export CSV
        </a>
    </div>

    {{-- Filters --}}
    <div class="card bg-base-200 shadow">
        <div class="card-body py-3 px-4">
            <form method="GET" class="flex flex-wrap gap-3 items-end">
                <div>
                    <label class="label label-text text-xs">Pair</label>
                    <select name="pair" class="select select-sm select-bordered">
                        <option value="">All Pairs</option>
                        @foreach($pairs as $p)
                        <option value="{{ $p }}" @selected(request('pair') === $p)>{{ $p }}</option>
                        @endforeach
                    </select>
                </div>
                <div>
                    <label class="label label-text text-xs">Direction</label>
                    <select name="direction" class="select select-sm select-bordered">
                        <option value="">All</option>
                        <option value="BUY"  @selected(request('direction') === 'BUY')>BUY</option>
                        <option value="SELL" @selected(request('direction') === 'SELL')>SELL</option>
                    </select>
                </div>
                <div>
                    <label class="label label-text text-xs">Status</label>
                    <select name="status" class="select select-sm select-bordered">
                        <option value="">All</option>
                        @foreach(['PENDING','WIN','LOSS','EXPIRED'] as $st)
                        <option value="{{ $st }}" @selected(request('status') === $st)>{{ $st }}</option>
                        @endforeach
                    </select>
                </div>
                {{-- NEW: Regime filter --}}
                <div>
                    <label class="label label-text text-xs">Regime</label>
                    <select name="regime" class="select select-sm select-bordered">
                        <option value="">All</option>
                        @foreach(['TRENDING','RANGING','VOLATILE','WEAK_TREND'] as $r)
                        <option value="{{ $r }}" @selected(request('regime') === $r)>{{ $r }}</option>
                        @endforeach
                    </select>
                </div>
                {{-- NEW: M15 filter --}}
                <div>
                    <label class="label label-text text-xs">M15</label>
                    <select name="m15" class="select select-sm select-bordered">
                        <option value="">All</option>
                        <option value="1" @selected(request('m15') === '1')>Confirmed ✅</option>
                    </select>
                </div>
                <div>
                    <label class="label label-text text-xs">From</label>
                    <input type="date" name="date_from" value="{{ request('date_from') }}"
                        class="input input-sm input-bordered">
                </div>
                <div>
                    <label class="label label-text text-xs">To</label>
                    <input type="date" name="date_to" value="{{ request('date_to') }}"
                        class="input input-sm input-bordered">
                </div>
                <button type="submit" class="btn btn-sm btn-primary">Filter</button>
                <a href="{{ route('signals.index') }}" class="btn btn-sm btn-ghost">Reset</a>
            </form>
        </div>
    </div>

    {{-- Signal Table --}}
    <div class="card bg-base-200 shadow-xl overflow-x-auto">
        <table class="table table-sm w-full text-xs">
            <thead class="text-xs uppercase opacity-60">
                <tr>
                    <th>ID</th>
                    <th>Pair</th>
                    <th>Dir</th>
                    <th>Entry</th>
                    <th>SL</th>
                    <th>TP1</th>
                    <th>RR</th>
                    <th>Score</th>
                    <th>Agree</th>
                    <th>Regime</th>
                    <th>Pattern</th>
                    <th>M15</th>
                    <th>Status</th>
                    <th>Pips</th>
                    <th>Time</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                @forelse($signals as $s)
                <tr class="hover">
                    <td class="font-mono opacity-50">{{ $s->id }}</td>
                    <td class="font-bold">{{ $s->pair }}</td>
                    <td>
                        <span class="badge badge-sm {{ $s->direction_badge }}">{{ $s->direction }}</span>
                    </td>
                    <td class="font-mono">{{ $s->entry_price }}</td>
                    <td class="font-mono text-error">{{ $s->stop_loss }}</td>
                    <td class="font-mono text-success">{{ $s->take_profit_1 }}</td>
                    <td class="font-mono text-xs opacity-70">{{ $s->risk_reward }}</td>
                    <td>
                        <span class="badge badge-sm {{ $s->confidence_badge }}">
                            {{ $s->consensus_score }}
                        </span>
                    </td>
                    {{-- NEW: Strategy agreement --}}
                    <td class="font-mono text-center">{{ $s->strategy_agreement }}</td>
                    {{-- NEW: Regime --}}
                    <td>
                        @if($s->market_regime)
                        <span class="badge badge-xs {{ $s->regime_badge }}">{{ $s->market_regime }}</span>
                        @else
                        <span class="opacity-30">—</span>
                        @endif
                    </td>
                    {{-- NEW: Pattern --}}
                    <td class="max-w-[80px] truncate" title="{{ $s->pattern_display }}">
                        {{ \Str::limit($s->pattern_display, 12) }}
                    </td>
                    {{-- NEW: M15 --}}
                    <td>
                        @if($s->m15_confirmed !== null)
                        <span class="badge badge-xs {{ $s->m15_badge }}">
                            {{ $s->m15_confirmed ? '✅' : '⏳' }}
                        </span>
                        @else
                        <span class="opacity-30">—</span>
                        @endif
                    </td>
                    <td>
                        <span class="badge badge-sm {{ $s->status_badge }}">{{ $s->status }}</span>
                    </td>
                    <td class="font-mono {{ ($s->pips_result ?? 0) >= 0 ? 'text-success' : 'text-error' }}">
                        {{ $s->pips_result !== null ? (($s->pips_result >= 0 ? '+' : '') . $s->pips_result) : '—' }}
                    </td>
                    <td class="opacity-60 whitespace-nowrap">
                        {{ $s->created_at?->format('d/m H:i') }}
                    </td>
                    {{-- Quick update form --}}
                    <td>
                        <form method="POST" action="{{ route('signals.update', $s) }}" class="flex gap-1">
                            @csrf @method('PATCH')
                            <select name="status" class="select select-xs select-bordered w-24">
                                @foreach(['PENDING','WIN','LOSS','EXPIRED'] as $st)
                                <option value="{{ $st }}" @selected($s->status === $st)>{{ $st }}</option>
                                @endforeach
                            </select>
                            <input type="number" name="pips_result" step="0.1"
                                class="input input-xs input-bordered w-16"
                                placeholder="pips"
                                value="{{ $s->pips_result }}">
                            <button class="btn btn-xs btn-primary">✓</button>
                        </form>
                    </td>
                </tr>
                @empty
                <tr><td colspan="16" class="text-center py-8 opacity-50">No signals found</td></tr>
                @endforelse
            </tbody>
        </table>

        {{-- Pagination --}}
        <div class="p-4">
            {{ $signals->links() }}
        </div>
    </div>

</div>
@endsection
