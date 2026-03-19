<?php

namespace App\Http\Controllers;

use App\Models\TelegramChannel;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class TelegramController extends Controller
{
    public function index()
    {
        $channels = TelegramChannel::orderBy('type')->get();
        return view('pages.telegram', compact('channels'));
    }

    public function store(Request $request)
    {
        $validated = $request->validate([
            'channel_name' => 'required|string|max:100',
            'chat_id'      => 'required|string|max:50|unique:telegram_channels,chat_id',
            'type'         => 'required|in:FREE,PREMIUM',
        ]);

        $validated['is_active'] = true;
        TelegramChannel::create($validated);

        return back()->with('success', 'Channel added successfully.');
    }

    public function sendTest(Request $request)
    {
        $request->validate([
            'chat_id' => 'required|string',
            'message' => 'required|string|max:4096',
        ]);

        $token = config('services.telegram.bot_token');

        $response = Http::post("https://api.telegram.org/bot{$token}/sendMessage", [
            'chat_id'    => $request->chat_id,
            'text'       => $request->message,
            'parse_mode' => 'HTML',
        ]);

        if ($response->successful() && $response->json('ok')) {
            return back()->with('success', 'Test message sent successfully.');
        }

        return back()->with('error', 'Failed: ' . ($response->json('description') ?? 'Unknown error'));
    }

    public function toggle(TelegramChannel $channel)
    {
        $channel->update(['is_active' => ! $channel->is_active]);
        $status = $channel->is_active ? 'activated' : 'deactivated';
        return back()->with('success', "Channel {$status}.");
    }

    public function destroy(TelegramChannel $channel)
    {
        $channel->delete();
        return back()->with('success', 'Channel removed.');
    }
}
