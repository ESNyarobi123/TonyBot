<?php

namespace App\Http\Controllers;

use App\Models\Signal;
use App\Models\Subscriber;
use App\Models\PairPerformance;
use Illuminate\Support\Facades\DB;

class DashboardController extends Controller
{
    public function index()
    {
        $stats         = $this->getTodayStats();
        $recentSignals = Signal::orderBy('created_at', 'desc')->limit(10)->get();
        $regimeStats   = $this->getRegimeStats();
        $filterStats   = $this->getFilterStats();

        return view('pages.dashboard', compact('stats', 'recentSignals', 'regimeStats', 'filterStats'));
    }

    private function getTodayStats(): array
    {
        $today = Signal::whereDate('created_at', today());
        $total   = $today->count();
        $wins    = $today->clone()->wins()->count();
        $losses  = $today->clone()->losses()->count();
        $winRate = ($wins + $losses) > 0
            ? round($wins / ($wins + $losses) * 100, 1)
            : 0.0;
        $totalPips = round((float) $today->clone()->sum('pips_result'), 1);

        // Institutional upgrade stats
        $m15Confirmed  = $today->clone()->m15Confirmed()->count();
        $withPattern   = $today->clone()->withPattern()->count();
        $highConf      = $today->clone()->highConfidence()->count();

        return [
            'total_signals'      => $total,
            'wins'               => $wins,
            'losses'             => $losses,
            'win_rate'           => $winRate,
            'total_pips'         => $totalPips,
            'active_subscribers' => Subscriber::active()->count(),
            // New institutional stats
            'm15_confirmed'      => $m15Confirmed,
            'with_pattern'       => $withPattern,
            'high_confidence'    => $highConf,
        ];
    }

    private function getRegimeStats(): array
    {
        return Signal::selectRaw('market_regime, COUNT(*) as total,
                SUM(CASE WHEN status = \'WIN\' THEN 1 ELSE 0 END) as wins')
            ->whereIn('status', ['WIN', 'LOSS'])
            ->whereNotNull('market_regime')
            ->groupBy('market_regime')
            ->get()
            ->keyBy('market_regime')
            ->toArray();
    }

    private function getFilterStats(): array
    {
        $last30 = Signal::where('created_at', '>=', now()->subDays(30));
        return [
            'avg_score'         => round((float) $last30->clone()->avg('consensus_score'), 1),
            'avg_m15_score'     => round((float) $last30->clone()->avg('m15_score'), 1),
            'm15_confirm_rate'  => round(
                $last30->clone()->m15Confirmed()->count() / max($last30->clone()->count(), 1) * 100, 1
            ),
            'pattern_signal_rate' => round(
                $last30->clone()->withPattern()->count() / max($last30->clone()->count(), 1) * 100, 1
            ),
        ];
    }
}
