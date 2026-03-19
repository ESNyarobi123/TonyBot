<?php

namespace App\Http\Controllers;

use App\Models\Signal;
use App\Models\PairPerformance;
use Illuminate\Support\Facades\DB;

class PerformanceController extends Controller
{
    public function index()
    {
        $byPair = PairPerformance::select('pair')
            ->selectRaw('SUM(signals_sent) as total_signals')
            ->selectRaw('SUM(wins) as total_wins')
            ->selectRaw('SUM(losses) as total_losses')
            ->selectRaw('ROUND(AVG(win_rate), 2) as avg_win_rate')
            ->selectRaw('SUM(total_pips) as total_pips')
            ->groupBy('pair')
            ->orderByDesc('avg_win_rate')
            ->get();

        $monthly = Signal::selectRaw("DATE_TRUNC('month', created_at) as month")
            ->selectRaw('COUNT(*) as total')
            ->selectRaw("SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END) as wins")
            ->selectRaw('SUM(pips_result) as pips')
            ->whereIn('status', ['WIN', 'LOSS'])
            ->groupByRaw("DATE_TRUNC('month', created_at)")
            ->orderBy('month', 'desc')
            ->limit(12)
            ->get();

        $byHour = Signal::selectRaw('EXTRACT(HOUR FROM created_at)::integer as hour')
            ->selectRaw("SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END)::float / NULLIF(SUM(CASE WHEN status IN ('WIN','LOSS') THEN 1 ELSE 0 END), 0) * 100 as win_rate")
            ->selectRaw('COUNT(*) as total')
            ->whereIn('status', ['WIN', 'LOSS'])
            ->groupByRaw('EXTRACT(HOUR FROM created_at)')
            ->orderBy('hour')
            ->get()
            ->keyBy('hour');

        return view('pages.performance', compact('byPair', 'monthly', 'byHour'));
    }
}
