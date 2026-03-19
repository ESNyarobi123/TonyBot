<?php

namespace App\Http\Controllers;

use App\Models\Signal;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\StreamedResponse;

class SignalController extends Controller
{
    public function index(Request $request)
    {
        $query = Signal::orderBy('created_at', 'desc');

        if ($request->filled('pair')) {
            $query->where('pair', $request->pair);
        }
        if ($request->filled('direction')) {
            $query->where('direction', $request->direction);
        }
        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }
        if ($request->filled('date_from')) {
            $query->whereDate('created_at', '>=', $request->date_from);
        }
        if ($request->filled('date_to')) {
            $query->whereDate('created_at', '<=', $request->date_to);
        }

        $signals = $query->paginate(25)->withQueryString();

        $pairs = Signal::select('pair')->distinct()->pluck('pair');

        return view('pages.signals', compact('signals', 'pairs'));
    }

    public function update(Request $request, Signal $signal)
    {
        $validated = $request->validate([
            'status'      => 'required|in:WIN,LOSS,EXPIRED,PENDING',
            'pips_result' => 'nullable|numeric',
        ]);

        if (in_array($validated['status'], ['WIN', 'LOSS'])) {
            $validated['closed_at'] = now();
        }

        $signal->update($validated);

        return back()->with('success', "Signal #{$signal->id} updated to {$validated['status']}");
    }

    public function exportCsv(Request $request): StreamedResponse
    {
        $signals = Signal::orderBy('created_at', 'desc')->get();

        $headers = [
            'Content-Type'        => 'text/csv',
            'Content-Disposition' => 'attachment; filename="signals_' . now()->format('Y-m-d') . '.csv"',
        ];

        return response()->stream(function () use ($signals) {
            $handle = fopen('php://output', 'w');
            fputcsv($handle, [
                'ID', 'Pair', 'Direction', 'Entry', 'SL', 'TP1', 'TP2', 'TP3',
                'Timeframe', 'Consensus', 'Confidence', 'Status', 'Pips', 'Created',
            ]);
            foreach ($signals as $s) {
                fputcsv($handle, [
                    $s->id, $s->pair, $s->direction, $s->entry_price,
                    $s->stop_loss, $s->take_profit_1, $s->take_profit_2, $s->take_profit_3,
                    $s->timeframe, $s->consensus_score, $s->confidence,
                    $s->status, $s->pips_result, $s->created_at,
                ]);
            }
            fclose($handle);
        }, 200, $headers);
    }
}
