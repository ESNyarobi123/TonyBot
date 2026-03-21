{{-- ERICKsky Dashboard — performance-stats Livewire component (v2 Institutional) --}}

<div>
    {{-- Period selector --}}
    <div class="flex flex-wrap gap-2 mb-5">
        @foreach(['today' => 'Today', 'week' => 'This Week', 'month' => 'This Month', 'all' => 'All Time'] as $val => $label)
        <button wire:click="setPeriod('{{ $val }}')"
            class="btn btn-sm {{ $period === $val ? 'btn-primary' : 'btn-ghost' }}">
            {{ $label }}
        </button>
        @endforeach
    </div>

    {{-- Row 1: Core KPIs --}}
    <div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4 mb-4">

        {{-- Total Signals --}}
        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs opacity-60">Signals</div>
            <div class="stat-value text-2xl font-bold">{{ $stats['total'] }}</div>
            <div class="stat-desc">{{ $stats['pending'] }} pending</div>
        </div>

        {{-- Win Rate --}}
        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs opacity-60">Win Rate</div>
            <div class="stat-value text-2xl font-bold {{ $stats['win_rate'] >= 60 ? 'text-success' : ($stats['win_rate'] >= 45 ? 'text-warning' : 'text-error') }}">
                {{ $stats['win_rate'] }}%
            </div>
            <div class="stat-desc">{{ $stats['wins'] }}W / {{ $stats['losses'] }}L</div>
        </div>

        {{-- Total Pips --}}
        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs opacity-60">Total Pips</div>
            <div class="stat-value text-2xl font-bold {{ $stats['total_pips'] >= 0 ? 'text-success' : 'text-error' }}">
                {{ $stats['total_pips'] >= 0 ? '+' : '' }}{{ $stats['total_pips'] }}
            </div>
            <div class="stat-desc">Closed trades</div>
        </div>

        {{-- Avg Score --}}
        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs opacity-60">Avg Score</div>
            <div class="stat-value text-2xl font-bold text-info">{{ $stats['avg_score'] }}</div>
            <div class="stat-desc">Consensus /100</div>
        </div>

        {{-- Subscribers --}}
        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs opacity-60">Subscribers</div>
            <div class="stat-value text-2xl font-bold text-secondary">{{ $stats['subscribers'] }}</div>
            <div class="stat-desc">Active members</div>
        </div>

        {{-- M15 Win Rate --}}
        <div class="stat bg-base-200 rounded-xl p-4 shadow border border-success/20">
            <div class="stat-title text-xs opacity-60">M15 Win Rate</div>
            <div class="stat-value text-2xl font-bold text-success">{{ $stats['m15_win_rate'] }}%</div>
            <div class="stat-desc">M15-confirmed only</div>
        </div>
    </div>

    {{-- Row 2: Institutional Upgrade Stats --}}
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">

        {{-- M15 Confirmed --}}
        <div class="flex items-center gap-3 bg-success/10 border border-success/20 rounded-xl p-3">
            <span class="text-2xl">📊</span>
            <div>
                <div class="text-lg font-bold">{{ $stats['m15_confirmed'] }}</div>
                <div class="text-xs opacity-60">M15 Confirmed</div>
            </div>
        </div>

        {{-- Pattern Confirmed --}}
        <div class="flex items-center gap-3 bg-info/10 border border-info/20 rounded-xl p-3">
            <span class="text-2xl">📐</span>
            <div>
                <div class="text-lg font-bold">{{ $stats['with_pattern'] }}</div>
                <div class="text-xs opacity-60">Pattern Detected</div>
            </div>
        </div>

        {{-- High Confidence --}}
        <div class="flex items-center gap-3 bg-warning/10 border border-warning/20 rounded-xl p-3">
            <span class="text-2xl">💎</span>
            <div>
                <div class="text-lg font-bold">{{ $stats['high_confidence'] }}</div>
                <div class="text-xs opacity-60">HIGH+ Confidence</div>
            </div>
        </div>

        {{-- Pending --}}
        <div class="flex items-center gap-3 bg-base-300 rounded-xl p-3">
            <span class="text-2xl">⏳</span>
            <div>
                <div class="text-lg font-bold">{{ $stats['pending'] }}</div>
                <div class="text-xs opacity-60">Pending Signals</div>
            </div>
        </div>
    </div>
</div>
