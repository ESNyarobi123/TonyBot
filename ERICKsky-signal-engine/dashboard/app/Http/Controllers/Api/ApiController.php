<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Signal;
use App\Models\Subscriber;
use App\Models\PairPerformance;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

/**
 * ERICKsky Signal Engine — REST API Controller
 *
 * All endpoints return JSON.  The dashboard JS fetches from here every 10s.
 *
 * Endpoints:
 *   GET /api/stats               — live KPI stats
 *   GET /api/signals             — paginated signal list with filters
 *   GET /api/signals/{id}        — single signal detail
 *   GET /api/performance         — pair + hourly + monthly performance
 *   GET /api/regime-stats        — regime breakdown with win rates
 *   GET /api/filter-stats        — institutional filter effectiveness
 *   GET /api/news-events         — upcoming high-impact news from local DB
 *   POST /api/signals/{id}/outcome — manually mark WIN/LOSS + pips
 */
class ApiController extends Controller
{
    // ── GET /api/stats ────────────────────────────────────────────────────────

    public function stats(): JsonResponse
    {
        $today  = Signal::whereDate('created_at', today());
        $total  = $today->count();
        $wins   = $today->clone()->wins()->count();
        $losses = $today->clone()->losses()->count();

        return response()->json([
            'today' => [
                'total'          => $total,
                'wins'           => $wins,
                'losses'         => $losses,
                'pending'        => $today->clone()->pending()->count(),
                'win_rate'       => ($wins + $losses) > 0
                    ? round($wins / ($wins + $losses) * 100, 1) : 0.0,
                'total_pips'     => round((float) $today->clone()->sum('pips_result'), 1),
                'm15_confirmed'  => $today->clone()->m15Confirmed()->count(),
                'with_pattern'   => $today->clone()->withPattern()->count(),
                'high_confidence' => $today->clone()->highConfidence()->count(),
            ],
            'global' => [
                'subscribers'    => Subscriber::active()->count(),
                'total_signals'  => Signal::count(),
                'overall_win_rate' => $this->overallWinRate(),
            ],
            'last_signal_at' => Signal::orderBy('created_at', 'desc')
                ->value('created_at'),
        ]);
    }

    // ── GET /api/signals ──────────────────────────────────────────────────────

    public function signals(Request $request): JsonResponse
    {
        $query = Signal::orderBy('created_at', 'desc');

        if ($request->filled('pair'))       $query->where('pair',      $request->pair);
        if ($request->filled('direction'))  $query->where('direction', $request->direction);
        if ($request->filled('status'))     $query->where('status',    $request->status);
        if ($request->filled('regime'))     $query->where('market_regime', $request->regime);
        if ($request->filled('confidence')) $query->where('confidence', $request->confidence);
        if ($request->filled('m15'))        $query->m15Confirmed();
        if ($request->filled('pattern'))    $query->withPattern();
        if ($request->filled('date_from'))  $query->whereDate('created_at', '>=', $request->date_from);
        if ($request->filled('date_to'))    $query->whereDate('created_at', '<=', $request->date_to);

        $signals = $query->paginate($request->get('per_page', 25));

        return response()->json([
            'data'  => $signals->map(fn($s) => $this->signalResource($s)),
            'meta'  => [
                'total'        => $signals->total(),
                'per_page'     => $signals->perPage(),
                'current_page' => $signals->currentPage(),
                'last_page'    => $signals->lastPage(),
            ],
        ]);
    }

    // ── GET /api/signals/{id} ─────────────────────────────────────────────────

    public function signal(Signal $signal): JsonResponse
    {
        return response()->json($this->signalResource($signal, detail: true));
    }

    // ── GET /api/performance ──────────────────────────────────────────────────

    public function performance(): JsonResponse
    {
        $byPair = PairPerformance::select('pair')
            ->selectRaw('SUM(signals_sent) as total_signals')
            ->selectRaw('SUM(wins) as total_wins')
            ->selectRaw('SUM(losses) as total_losses')
            ->selectRaw('ROUND(AVG(win_rate)::numeric, 2) as avg_win_rate')
            ->selectRaw('SUM(total_pips) as total_pips')
            ->groupBy('pair')
            ->orderByDesc('avg_win_rate')
            ->get();

        $byHour = Signal::selectRaw('EXTRACT(HOUR FROM created_at)::integer as hour')
            ->selectRaw("ROUND((SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(CASE WHEN status IN ('WIN','LOSS') THEN 1 END), 0) * 100)::numeric, 1) as win_rate")
            ->selectRaw('COUNT(*) as total')
            ->whereIn('status', ['WIN', 'LOSS'])
            ->groupByRaw('EXTRACT(HOUR FROM created_at)')
            ->orderBy('hour')
            ->get()
            ->keyBy('hour');

        $monthly = Signal::selectRaw("DATE_TRUNC('month', created_at) as month")
            ->selectRaw('COUNT(*) as total')
            ->selectRaw("SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END) as wins")
            ->selectRaw('ROUND(SUM(pips_result)::numeric, 1) as pips')
            ->whereIn('status', ['WIN', 'LOSS'])
            ->groupByRaw("DATE_TRUNC('month', created_at)")
            ->orderBy('month', 'desc')
            ->limit(12)
            ->get();

        return response()->json(compact('byPair', 'byHour', 'monthly'));
    }

    // ── GET /api/regime-stats ─────────────────────────────────────────────────

    public function regimeStats(): JsonResponse
    {
        $stats = Signal::selectRaw("market_regime,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'LOSS' THEN 1 ELSE 0 END) as losses,
                ROUND((SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END)::float /
                    NULLIF(SUM(CASE WHEN status IN ('WIN','LOSS') THEN 1 ELSE 0 END),0)*100)::numeric, 1) as win_rate,
                ROUND(SUM(pips_result)::numeric, 1) as total_pips")
            ->whereIn('status', ['WIN', 'LOSS'])
            ->whereNotNull('market_regime')
            ->groupBy('market_regime')
            ->orderByDesc('win_rate')
            ->get();

        return response()->json($stats);
    }

    // ── GET /api/filter-stats ─────────────────────────────────────────────────

    public function filterStats(): JsonResponse
    {
        $base = Signal::whereIn('status', ['WIN', 'LOSS']);

        // M15 confirmed vs unconfirmed
        $m15 = $base->clone()
            ->selectRaw("m15_confirmed,
                COUNT(*) as total,
                SUM(CASE WHEN status='WIN' THEN 1 ELSE 0 END) as wins,
                ROUND((SUM(CASE WHEN status='WIN' THEN 1 ELSE 0 END)::float/NULLIF(COUNT(*),0)*100)::numeric,1) as win_rate")
            ->groupBy('m15_confirmed')
            ->get()
            ->keyBy('m15_confirmed');

        // Pattern confirmed vs no pattern
        $pattern = $base->clone()
            ->selectRaw("(pattern_names IS NOT NULL AND pattern_names::text != '[]') as has_pattern,
                COUNT(*) as total,
                SUM(CASE WHEN status='WIN' THEN 1 ELSE 0 END) as wins,
                ROUND((SUM(CASE WHEN status='WIN' THEN 1 ELSE 0 END)::float/NULLIF(COUNT(*),0)*100)::numeric,1) as win_rate")
            ->groupByRaw("(pattern_names IS NOT NULL AND pattern_names::text != '[]')")
            ->get()
            ->keyBy('has_pattern');

        // Score brackets
        $scoreBrackets = $base->clone()
            ->selectRaw("
                CASE
                    WHEN consensus_score >= 90 THEN '90-100'
                    WHEN consensus_score >= 80 THEN '80-89'
                    WHEN consensus_score >= 70 THEN '70-79'
                    ELSE '<70'
                END as bracket,
                COUNT(*) as total,
                ROUND((SUM(CASE WHEN status='WIN' THEN 1 ELSE 0 END)::float/NULLIF(COUNT(*),0)*100)::numeric,1) as win_rate")
            ->groupByRaw("CASE
                WHEN consensus_score >= 90 THEN '90-100'
                WHEN consensus_score >= 80 THEN '80-89'
                WHEN consensus_score >= 70 THEN '70-79'
                ELSE '<70' END")
            ->orderByDesc('win_rate')
            ->get();

        return response()->json(compact('m15', 'pattern', 'scoreBrackets'));
    }

    // ── GET /api/news-events ───────────────────────────────────────────────────

    public function newsEvents(Request $request): JsonResponse
    {
        $now    = now();
        $window = $request->get('hours', 24);

        $events = DB::table('news_events')
            ->where('event_time', '>=', $now)
            ->where('event_time', '<=', $now->copy()->addHours($window))
            ->orderBy('event_time')
            ->get(['title', 'currency', 'impact', 'event_time']);

        return response()->json(['events' => $events, 'window_hours' => $window]);
    }

    // ── POST /api/signals/{id}/outcome ────────────────────────────────────────

    public function recordOutcome(Request $request, Signal $signal): JsonResponse
    {
        $validated = $request->validate([
            'status'      => 'required|in:WIN,LOSS,EXPIRED',
            'pips_result' => 'nullable|numeric|between:-500,500',
        ]);

        $signal->update(array_merge($validated, [
            'closed_at' => now(),
        ]));

        return response()->json([
            'success' => true,
            'signal'  => $this->signalResource($signal->fresh()),
        ]);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private function signalResource(Signal $s, bool $detail = false): array
    {
        $base = [
            'id'             => $s->id,
            'pair'           => $s->pair,
            'direction'      => $s->direction,
            'entry_price'    => $s->entry_price,
            'stop_loss'      => $s->stop_loss,
            'take_profit_1'  => $s->take_profit_1,
            'take_profit_2'  => $s->take_profit_2,
            'take_profit_3'  => $s->take_profit_3,
            'consensus_score' => $s->consensus_score,
            'confidence'     => $s->confidence,
            'status'         => $s->status,
            'pips_result'    => $s->pips_result,
            'risk_reward'    => $s->risk_reward,
            // Institutional fields
            'market_regime'  => $s->market_regime,
            'm15_confirmed'  => $s->m15_confirmed,
            'm15_score'      => $s->m15_score,
            'pattern_names'  => $s->pattern_names ?? [],
            'pattern_display' => $s->pattern_display,
            'strategy_agreement' => $s->strategy_agreement,
            'created_at'     => $s->created_at?->toIso8601String(),
            'sent_at'        => $s->sent_at?->toIso8601String(),
            'closed_at'      => $s->closed_at?->toIso8601String(),
        ];

        if ($detail) {
            $base['strategy_scores']     = $s->strategy_scores;
            $base['strategy_directions'] = $s->strategy_directions;
            $base['filters_passed']      = $s->filters_passed;
        }

        return $base;
    }

    private function overallWinRate(): float
    {
        $wins   = Signal::wins()->count();
        $losses = Signal::losses()->count();
        return ($wins + $losses) > 0
            ? round($wins / ($wins + $losses) * 100, 1)
            : 0.0;
    }
}
