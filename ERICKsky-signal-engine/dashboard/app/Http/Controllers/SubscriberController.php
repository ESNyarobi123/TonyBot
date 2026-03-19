<?php

namespace App\Http\Controllers;

use App\Models\Subscriber;
use Illuminate\Http\Request;

class SubscriberController extends Controller
{
    public function index()
    {
        $subscribers = Subscriber::orderBy('created_at', 'desc')->paginate(30);
        return view('pages.subscribers', compact('subscribers'));
    }

    public function store(Request $request)
    {
        $validated = $request->validate([
            'telegram_chat_id' => 'required|string|max:50|unique:subscribers,telegram_chat_id',
            'username'         => 'nullable|string|max:100',
            'full_name'        => 'nullable|string|max:200',
            'plan'             => 'required|in:FREE,BASIC,PREMIUM',
            'expires_at'       => 'nullable|date',
        ]);

        $validated['subscribed_at'] = now();
        $validated['is_active']     = true;
        Subscriber::create($validated);

        return back()->with('success', 'Subscriber added successfully.');
    }

    public function update(Request $request, Subscriber $subscriber)
    {
        $validated = $request->validate([
            'plan'       => 'required|in:FREE,BASIC,PREMIUM',
            'is_active'  => 'boolean',
            'expires_at' => 'nullable|date',
        ]);

        $subscriber->update($validated);
        return back()->with('success', 'Subscriber updated.');
    }

    public function destroy(Subscriber $subscriber)
    {
        $subscriber->update(['is_active' => false]);
        return back()->with('success', 'Subscriber deactivated.');
    }
}
