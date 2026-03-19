<?php

namespace App\Http\Livewire;

use App\Models\TelegramChannel;
use Livewire\Component;
use Illuminate\Support\Facades\Http;

class TelegramManager extends Component
{
    public string $channelName = '';
    public string $chatId = '';
    public string $type = 'FREE';
    public string $testMessage = '';
    public string $testChatId = '';
    public ?string $feedbackMessage = null;
    public bool $feedbackSuccess = true;

    protected $rules = [
        'channelName' => 'required|string|max:100',
        'chatId'      => 'required|string|max:50',
        'type'        => 'required|in:FREE,PREMIUM',
    ];

    public function addChannel(): void
    {
        $this->validate();

        if (TelegramChannel::where('chat_id', $this->chatId)->exists()) {
            $this->feedbackMessage = 'Chat ID already exists.';
            $this->feedbackSuccess = false;
            return;
        }

        TelegramChannel::create([
            'channel_name' => $this->channelName,
            'chat_id'      => $this->chatId,
            'type'         => $this->type,
            'is_active'    => true,
        ]);

        $this->reset(['channelName', 'chatId', 'type']);
        $this->feedbackMessage = 'Channel added successfully.';
        $this->feedbackSuccess = true;
    }

    public function sendTestMessage(): void
    {
        $this->validate([
            'testChatId'    => 'required|string',
            'testMessage'   => 'required|string|max:4096',
        ]);

        $token = config('services.telegram.bot_token');
        $response = Http::post("https://api.telegram.org/bot{$token}/sendMessage", [
            'chat_id'    => $this->testChatId,
            'text'       => $this->testMessage,
            'parse_mode' => 'HTML',
        ]);

        if ($response->successful() && $response->json('ok')) {
            $this->feedbackMessage = 'Test message sent!';
            $this->feedbackSuccess = true;
            $this->reset(['testMessage']);
        } else {
            $this->feedbackMessage = 'Failed: ' . ($response->json('description') ?? 'Unknown error');
            $this->feedbackSuccess = false;
        }
    }

    public function toggleChannel(int $id): void
    {
        $channel = TelegramChannel::find($id);
        if ($channel) {
            $channel->update(['is_active' => ! $channel->is_active]);
        }
    }

    public function render()
    {
        $channels = TelegramChannel::orderBy('type')->orderBy('channel_name')->get();
        return view('livewire.telegram-manager', compact('channels'));
    }
}
