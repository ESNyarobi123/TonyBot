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

        $winRate   = ($wins + $losses) > 0
            ? round($wins / ($wins + $losses) * 100, 1)
            : 0.0;
        $totalPips = round((float) $query->clone()->sum('pips_result'), 1);

        // Institutional upgrade stats
        $m15Confirmed  = $query->clone()->m15Confirmed()->count();
        $withPattern   = $query->clone()->withPattern()->count();
        $highConf      = $query->clone()->highConfidence()->count();
        $avgScore      = round((float) $query->clone()->avg('consensus_score'), 1);

        // M15 win rate boost comparison
        $m15WinRate = 0.0;
        $m15Total   = $query->clone()->m15Confirmed()->whereIn('status', ['WIN', 'LOSS'])->count();
        if ($m15Total > 0) {
            $m15Wins    = $query->clone()->m15Confirmed()->wins()->count();
            $m15WinRate = round($m15Wins / $m15Total * 100, 1);
        }

        $stats = [
            'total'           => $total,
            'wins'            => $wins,
            'losses'          => $losses,
            'pending'         => $pending,
            'win_rate'        => $winRate,
            'total_pips'      => $totalPips,
            'subscribers'     => Subscriber::active()->count(),
            // Institutional
            'm15_confirmed'   => $m15Confirmed,
            'with_pattern'    => $withPattern,
            'high_confidence' => $highConf,
            'avg_score'       => $avgScore,
            'm15_win_rate'    => $m15WinRate,
        ];

        return view('livewire.performance-stats', compact('stats'));
    }

    public function setPeriod(string $period): void
    {
        $this->period = $period;
    }
}
