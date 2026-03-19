<div class="space-y-6">

    {{-- Feedback Alert --}}
    @if($feedbackMessage)
    <div class="alert {{ $feedbackSuccess ? 'alert-success' : 'alert-error' }}">
        <span>{{ $feedbackMessage }}</span>
        <button wire:click="$set('feedbackMessage', null)" class="btn btn-ghost btn-xs ml-auto">✕</button>
    </div>
    @endif

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {{-- Add Channel Form --}}
        <div class="card bg-base-200 shadow-xl">
            <div class="card-body">
                <h2 class="card-title">Add Channel</h2>
                <div class="space-y-3">
                    <div class="form-control">
                        <label class="label"><span class="label-text">Channel Name</span></label>
                        <input wire:model="channelName" type="text" class="input input-bordered"
                               placeholder="ERICKsky Signals">
                        @error('channelName') <span class="text-error text-xs mt-1">{{ $message }}</span> @enderror
                    </div>
                    <div class="form-control">
                        <label class="label"><span class="label-text">Chat ID</span></label>
                        <input wire:model="chatId" type="text" class="input input-bordered"
                               placeholder="-100xxxxxxxxx">
                        @error('chatId') <span class="text-error text-xs mt-1">{{ $message }}</span> @enderror
                    </div>
                    <div class="form-control">
                        <label class="label"><span class="label-text">Channel Type</span></label>
                        <select wire:model="type" class="select select-bordered">
                            <option value="FREE">Free</option>
                            <option value="PREMIUM">Premium</option>
                        </select>
                    </div>
                    <button wire:click="addChannel" class="btn btn-primary w-full">
                        <span wire:loading wire:target="addChannel" class="loading loading-spinner loading-sm"></span>
                        Add Channel
                    </button>
                </div>
            </div>
        </div>

        {{-- Test Message --}}
        <div class="card bg-base-200 shadow-xl">
            <div class="card-body">
                <h2 class="card-title">Send Test Message</h2>
                <div class="space-y-3">
                    <div class="form-control">
                        <label class="label"><span class="label-text">Chat ID / Channel</span></label>
                        <input wire:model="testChatId" type="text" class="input input-bordered"
                               placeholder="-100xxxxxxxxx or @channel">
                        @error('testChatId') <span class="text-error text-xs mt-1">{{ $message }}</span> @enderror
                    </div>
                    <div class="form-control">
                        <label class="label"><span class="label-text">Message (HTML supported)</span></label>
                        <textarea wire:model="testMessage" class="textarea textarea-bordered h-28"
                                  placeholder="<b>Test message</b> from ERICKsky Signal Engine"></textarea>
                        @error('testMessage') <span class="text-error text-xs mt-1">{{ $message }}</span> @enderror
                    </div>
                    <button wire:click="sendTestMessage" class="btn btn-secondary w-full">
                        <span wire:loading wire:target="sendTestMessage" class="loading loading-spinner loading-sm"></span>
                        Send Test
                    </button>
                </div>
            </div>
        </div>
    </div>

    {{-- Channels Table --}}
    <div class="card bg-base-200 shadow-xl">
        <div class="card-body">
            <h2 class="card-title">Active Channels</h2>
            @if($channels->isEmpty())
            <div class="text-center py-8 text-base-content/40">No channels configured yet.</div>
            @else
            <div class="overflow-x-auto">
                <table class="table table-sm">
                    <thead>
                        <tr><th>Name</th><th>Chat ID</th><th>Type</th><th>Subscribers</th><th>Status</th><th>Actions</th></tr>
                    </thead>
                    <tbody>
                        @foreach($channels as $channel)
                        <tr>
                            <td class="font-semibold">{{ $channel->channel_name }}</td>
                            <td class="font-mono text-xs text-base-content/60">{{ $channel->chat_id }}</td>
                            <td>
                                <span class="badge badge-sm {{ $channel->type_badge }}">{{ $channel->type }}</span>
                            </td>
                            <td class="text-center">{{ $channel->subscribers_count }}</td>
                            <td>
                                <span class="badge badge-sm {{ $channel->is_active ? 'badge-success' : 'badge-neutral' }}">
                                    {{ $channel->is_active ? 'Active' : 'Inactive' }}
                                </span>
                            </td>
                            <td>
                                <button wire:click="toggleChannel({{ $channel->id }})"
                                        class="btn btn-ghost btn-xs {{ $channel->is_active ? 'text-warning' : 'text-success' }}">
                                    {{ $channel->is_active ? 'Disable' : 'Enable' }}
                                </button>
                                <button wire:click="$set('testChatId', '{{ $channel->chat_id }}')"
                                        class="btn btn-ghost btn-xs">
                                    Test
                                </button>
                            </td>
                        </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
            @endif
        </div>
    </div>

</div>
