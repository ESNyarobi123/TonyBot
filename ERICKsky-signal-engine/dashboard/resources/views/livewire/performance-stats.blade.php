<div class="space-y-4">

    {{-- Period Tabs --}}
    <div class="tabs tabs-boxed bg-base-200 w-fit">
        <button wire:click="setPeriod('today')"
                class="tab {{ $period === 'today' ? 'tab-active' : '' }}">Today</button>
        <button wire:click="setPeriod('week')"
                class="tab {{ $period === 'week' ? 'tab-active' : '' }}">This Week</button>
        <button wire:click="setPeriod('month')"
                class="tab {{ $period === 'month' ? 'tab-active' : '' }}">This Month</button>
        <button wire:click="setPeriod('all')"
                class="tab {{ $period === 'all' ? 'tab-active' : '' }}">All Time</button>
    </div>

    {{-- Stats Row --}}
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">

        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs">Signals</div>
            <div class="stat-value text-2xl text-primary">{{ $stats['total'] }}</div>
        </div>

        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs">Wins</div>
            <div class="stat-value text-2xl text-success">{{ $stats['wins'] }}</div>
        </div>

        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs">Losses</div>
            <div class="stat-value text-2xl text-error">{{ $stats['losses'] }}</div>
        </div>

        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs">Win Rate</div>
            <div class="stat-value text-2xl {{ $stats['win_rate'] >= 60 ? 'text-success' : ($stats['win_rate'] >= 50 ? 'text-warning' : 'text-error') }}">
                {{ $stats['win_rate'] }}%
            </div>
        </div>

        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs">Total Pips</div>
            <div class="stat-value text-2xl {{ $stats['total_pips'] >= 0 ? 'text-success' : 'text-error' }}">
                {{ $stats['total_pips'] >= 0 ? '+' : '' }}{{ $stats['total_pips'] }}
            </div>
        </div>

        <div class="stat bg-base-200 rounded-xl p-4 shadow">
            <div class="stat-title text-xs">Subscribers</div>
            <div class="stat-value text-2xl text-accent">{{ $stats['subscribers'] }}</div>
        </div>

    </div>

    {{-- Win Rate Progress Bar --}}
    @if($stats['wins'] + $stats['losses'] > 0)
    <div class="bg-base-200 rounded-xl p-4">
        <div class="flex justify-between text-xs text-base-content/60 mb-2">
            <span>Win Rate Progress</span>
            <span>{{ $stats['wins'] }}W / {{ $stats['losses'] }}L</span>
        </div>
        <div class="flex rounded-full overflow-hidden h-4">
            @php $wr = $stats['win_rate']; @endphp
            <div class="bg-success transition-all duration-500" style="width: {{ $wr }}%"></div>
            <div class="bg-error transition-all duration-500" style="width: {{ 100 - $wr }}%"></div>
        </div>
        <div class="flex justify-between text-xs mt-1">
            <span class="text-success">{{ $wr }}% Win</span>
            <span class="text-error">{{ round(100 - $wr, 1) }}% Loss</span>
        </div>
    </div>
    @endif

</div>
