@extends('layouts.app')
@section('title', 'Signals — ERICKsky Signal Engine')

@section('content')
<div class="space-y-6">

    <div class="flex items-center justify-between flex-wrap gap-3">
        <h1 class="text-2xl font-bold">Signal History</h1>
        <a href="{{ route('signals.export') }}" class="btn btn-outline btn-sm gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            Export CSV
        </a>
    </div>

    {{-- Filters --}}
    <div class="card bg-base-200 shadow">
        <div class="card-body py-4">
            <form method="GET" class="flex flex-wrap gap-3 items-end">
                <div class="form-control">
                    <label class="label py-1"><span class="label-text text-xs">Pair</span></label>
                    <select name="pair" class="select select-bordered select-sm w-36">
                        <option value="">All Pairs</option>
                        @foreach($pairs as $pair)
                            <option value="{{ $pair }}" {{ request('pair') === $pair ? 'selected' : '' }}>{{ $pair }}</option>
                        @endforeach
                    </select>
                </div>
                <div class="form-control">
                    <label class="label py-1"><span class="label-text text-xs">Direction</span></label>
                    <select name="direction" class="select select-bordered select-sm w-28">
                        <option value="">All</option>
                        <option value="BUY" {{ request('direction') === 'BUY' ? 'selected' : '' }}>BUY</option>
                        <option value="SELL" {{ request('direction') === 'SELL' ? 'selected' : '' }}>SELL</option>
                    </select>
                </div>
                <div class="form-control">
                    <label class="label py-1"><span class="label-text text-xs">Status</span></label>
                    <select name="status" class="select select-bordered select-sm w-28">
                        <option value="">All</option>
                        <option value="PENDING" {{ request('status') === 'PENDING' ? 'selected' : '' }}>Pending</option>
                        <option value="WIN" {{ request('status') === 'WIN' ? 'selected' : '' }}>Win</option>
                        <option value="LOSS" {{ request('status') === 'LOSS' ? 'selected' : '' }}>Loss</option>
                        <option value="EXPIRED" {{ request('status') === 'EXPIRED' ? 'selected' : '' }}>Expired</option>
                    </select>
                </div>
                <div class="form-control">
                    <label class="label py-1"><span class="label-text text-xs">From</span></label>
                    <input type="date" name="date_from" value="{{ request('date_from') }}" class="input input-bordered input-sm w-36">
                </div>
                <div class="form-control">
                    <label class="label py-1"><span class="label-text text-xs">To</span></label>
                    <input type="date" name="date_to" value="{{ request('date_to') }}" class="input input-bordered input-sm w-36">
                </div>
                <button type="submit" class="btn btn-primary btn-sm">Filter</button>
                <a href="{{ route('signals.index') }}" class="btn btn-ghost btn-sm">Reset</a>
            </form>
        </div>
    </div>

    {{-- Table --}}
    <div class="card bg-base-200 shadow-xl overflow-x-auto">
        <table class="table table-zebra table-sm">
            <thead>
                <tr class="text-base-content/70">
                    <th>ID</th><th>Pair</th><th>Dir</th><th>Entry</th>
                    <th>SL</th><th>TP1</th><th>R:R</th><th>TF</th>
                    <th>Score</th><th>Confidence</th><th>Status</th>
                    <th>Pips</th><th>Date</th><th>Action</th>
                </tr>
            </thead>
            <tbody>
                @forelse($signals as $signal)
                <tr>
                    <td class="font-mono text-xs text-base-content/50">{{ $signal->id }}</td>
                    <td class="font-bold">{{ $signal->pair }}</td>
                    <td>
                        <span class="badge badge-sm {{ $signal->direction_badge }}">
                            {{ $signal->direction }}
                        </span>
                    </td>
                    <td class="font-mono text-xs">{{ number_format($signal->entry_price, 5) }}</td>
                    <td class="font-mono text-xs text-error">{{ number_format($signal->stop_loss, 5) }}</td>
                    <td class="font-mono text-xs text-success">{{ number_format($signal->take_profit_1, 5) }}</td>
                    <td class="text-xs">{{ $signal->risk_reward }}</td>
                    <td class="text-xs">{{ strtoupper($signal->timeframe) }}</td>
                    <td>
                        <div class="radial-progress text-primary text-xs"
                             style="--value:{{ $signal->consensus_score }}; --size:2rem; --thickness:3px">
                            {{ $signal->consensus_score }}
                        </div>
                    </td>
                    <td>
                        <span class="badge badge-sm {{ $signal->confidence_badge }}">
                            {{ str_replace('_', ' ', $signal->confidence) }}
                        </span>
                    </td>
                    <td>
                        <span class="badge badge-sm {{ $signal->status_badge }}">{{ $signal->status }}</span>
                    </td>
                    <td class="font-mono text-xs {{ $signal->pips_result > 0 ? 'text-success' : ($signal->pips_result < 0 ? 'text-error' : '') }}">
                        {{ $signal->pips_result !== null ? number_format($signal->pips_result, 1) : '—' }}
                    </td>
                    <td class="text-xs text-base-content/60">
                        {{ $signal->created_at?->format('d M H:i') }}
                    </td>
                    <td>
                        @if($signal->status === 'PENDING')
                        <div class="flex gap-1">
                            <form method="POST" action="{{ route('signals.update', $signal) }}">
                                @csrf @method('PATCH')
                                <input type="hidden" name="status" value="WIN">
                                <button class="btn btn-success btn-xs">WIN</button>
                            </form>
                            <form method="POST" action="{{ route('signals.update', $signal) }}">
                                @csrf @method('PATCH')
                                <input type="hidden" name="status" value="LOSS">
                                <button class="btn btn-error btn-xs">LOSS</button>
                            </form>
                        </div>
                        @else
                        <span class="text-xs text-base-content/40">—</span>
                        @endif
                    </td>
                </tr>
                @empty
                <tr>
                    <td colspan="14" class="text-center py-8 text-base-content/40">No signals found.</td>
                </tr>
                @endforelse
            </tbody>
        </table>
    </div>

    {{-- Pagination --}}
    <div class="flex justify-center">
        {{ $signals->links() }}
    </div>

</div>
@endsection
