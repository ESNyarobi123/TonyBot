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
        $stats = $this->getTodayStats();
        $recentSignals = Signal::orderBy('created_at', 'desc')->limit(10)->get();

        return view('pages.dashboard', compact('stats', 'recentSignals'));
    }

    private function getTodayStats(): array
    {
        $today = Signal::whereDate('created_at', today());
        $total = $today->count();
        $wins = $today->clone()->wins()->count();
        $losses = $today->clone()->losses()->count();
        $winRate = ($wins + $losses) > 0
            ? round($wins / ($wins + $losses) * 100, 1)
            : 0.0;
        $totalPips = $today->clone()->sum('pips_result') ?? 0;

        return [
            'total_signals'      => $total,
            'wins'               => $wins,
            'losses'             => $losses,
            'win_rate'           => $winRate,
            'total_pips'         => round($totalPips, 1),
            'active_subscribers' => Subscriber::active()->count(),
        ];
    }
}
