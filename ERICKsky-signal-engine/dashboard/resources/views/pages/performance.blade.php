@extends('layouts.app')
@section('title', 'Performance — ERICKsky Signal Engine')

@section('content')
<div class="space-y-6">

    <h1 class="text-2xl font-bold">Performance Analytics</h1>

    {{-- By Pair Table --}}
    <div class="card bg-base-200 shadow-xl">
        <div class="card-body">
            <h2 class="card-title text-lg">Win Rate by Pair (Last 30 Days)</h2>
            <div class="overflow-x-auto">
                <table class="table table-sm">
                    <thead>
                        <tr><th>Pair</th><th>Signals</th><th>Wins</th><th>Losses</th><th>Win Rate</th><th>Total Pips</th><th>Progress</th></tr>
                    </thead>
                    <tbody>
                        @forelse($byPair as $row)
                        <tr>
                            <td class="font-bold">{{ $row->pair }}</td>
                            <td>{{ $row->total_signals }}</td>
                            <td class="text-success">{{ $row->total_wins }}</td>
                            <td class="text-error">{{ $row->total_losses }}</td>
                            <td class="font-bold {{ $row->avg_win_rate >= 60 ? 'text-success' : ($row->avg_win_rate >= 50 ? 'text-warning' : 'text-error') }}">
                                {{ number_format($row->avg_win_rate, 1) }}%
                            </td>
                            <td class="font-mono {{ $row->total_pips >= 0 ? 'text-success' : 'text-error' }}">
                                {{ number_format($row->total_pips, 1) }}
                            </td>
                            <td class="w-32">
                                <progress class="progress {{ $row->avg_win_rate >= 60 ? 'progress-success' : ($row->avg_win_rate >= 50 ? 'progress-warning' : 'progress-error') }} w-32"
                                    value="{{ $row->avg_win_rate }}" max="100"></progress>
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="7" class="text-center py-6 text-base-content/40">No performance data yet.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    {{-- Monthly Performance --}}
    <div class="card bg-base-200 shadow-xl">
        <div class="card-body">
            <h2 class="card-title text-lg">Monthly Summary</h2>
            <div class="overflow-x-auto">
                <table class="table table-sm">
                    <thead>
                        <tr><th>Month</th><th>Signals</th><th>Wins</th><th>Pips</th><th>Win Rate</th></tr>
                    </thead>
                    <tbody>
                        @forelse($monthly as $row)
                        @php
                            $wr = $row->total > 0 ? round($row->wins / $row->total * 100, 1) : 0;
                        @endphp
                        <tr>
                            <td class="font-semibold">{{ \Carbon\Carbon::parse($row->month)->format('M Y') }}</td>
                            <td>{{ $row->total }}</td>
                            <td class="text-success">{{ $row->wins }}</td>
                            <td class="font-mono {{ $row->pips >= 0 ? 'text-success' : 'text-error' }}">
                                {{ number_format($row->pips ?? 0, 1) }}
                            </td>
                            <td class="{{ $wr >= 60 ? 'text-success font-bold' : ($wr >= 50 ? 'text-warning' : 'text-error') }}">
                                {{ $wr }}%
                            </td>
                        </tr>
                        @empty
                        <tr><td colspan="5" class="text-center py-6 text-base-content/40">No data.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    {{-- Best Hours Heatmap --}}
    <div class="card bg-base-200 shadow-xl">
        <div class="card-body">
            <h2 class="card-title text-lg">Best Trading Hours (UTC)</h2>
            <div class="grid grid-cols-12 gap-1 mt-2">
                @for($h = 0; $h < 24; $h++)
                @php
                    $hourData = $byHour->get($h);
                    $wr = $hourData ? round($hourData->win_rate ?? 0, 0) : 0;
                    $total = $hourData ? $hourData->total : 0;
                    $intensity = $wr >= 70 ? 'bg-success' : ($wr >= 55 ? 'bg-warning' : ($total > 0 ? 'bg-error' : 'bg-base-300'));
                    $opacity = $total > 0 ? 'opacity-90' : 'opacity-20';
                @endphp
                <div class="tooltip" data-tip="{{ sprintf('%02d:00 UTC', $h) }} — {{ $total }} signals, {{ $wr }}% WR">
                    <div class="h-10 rounded {{ $intensity }} {{ $opacity }} flex items-center justify-center text-xs font-bold cursor-default">
                        {{ sprintf('%02d', $h) }}
                    </div>
                </div>
                @endfor
            </div>
            <div class="flex gap-4 mt-3 text-xs text-base-content/60">
                <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-success"></span> ≥70% WR</span>
                <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-warning"></span> 55–70%</span>
                <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-error"></span> &lt;55%</span>
                <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-base-300 opacity-20"></span> No data</span>
            </div>
        </div>
    </div>

</div>
@endsection
