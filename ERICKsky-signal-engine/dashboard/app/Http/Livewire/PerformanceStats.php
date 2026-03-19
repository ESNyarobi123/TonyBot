<?php

namespace App\Http\Livewire;

use App\Models\Signal;
use App\Models\Subscriber;
use Livewire\Component;

class PerformanceStats extends Component
{
    public string $period = 'today';  // today | week | month | all

    public function render()
    {
        $query = Signal::query();

        match ($this->period) {
            'today' => $query->whereDate('created_at', today()),
            'week'  => $query->where('created_at', '>=', now()->startOfWeek()),
            'month' => $query->where('created_at', '>=', now()->startOfMonth()),
            default => $query,
        };

        $total   = $query->clone()->count();
        $wins    = $query->clone()->wins()->count();
        $losses  = $query->clone()->losses()->count();
        $pending = $query->clone()->pending()->count();

        $winRate  = ($wins + $losses) > 0
            ? round($wins / ($wins + $losses) * 100, 1)
            : 0.0;
        $totalPips = round((float) $query->clone()->sum('pips_result'), 1);

        $stats = [
            'total'       => $total,
            'wins'        => $wins,
            'losses'      => $losses,
            'pending'     => $pending,
            'win_rate'    => $winRate,
            'total_pips'  => $totalPips,
            'subscribers' => Subscriber::active()->count(),
        ];

        return view('livewire.performance-stats', compact('stats'));
    }

    public function setPeriod(string $period): void
    {
        $this->period = $period;
    }
}
