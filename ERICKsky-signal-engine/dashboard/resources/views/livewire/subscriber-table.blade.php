<div class="space-y-4">

    {{-- Search + Filter Bar --}}
    <div class="flex flex-wrap gap-3 items-center">
        <input wire:model.live.debounce.300ms="search"
               type="text" placeholder="Search name, username, chat ID..."
               class="input input-bordered input-sm flex-1 min-w-48">

        <select wire:model.live="planFilter" class="select select-bordered select-sm w-32">
            <option value="">All Plans</option>
            <option value="FREE">Free</option>
            <option value="BASIC">Basic</option>
            <option value="PREMIUM">Premium</option>
        </select>

        <div wire:loading class="loading loading-spinner loading-sm text-primary"></div>
    </div>

    {{-- Table --}}
    <div class="card bg-base-200 shadow-xl overflow-x-auto">
        <table class="table table-zebra table-sm">
            <thead>
                <tr class="text-base-content/70">
                    <th>
                        <button wire:click="sortBy('full_name')" class="flex items-center gap-1">
                            Name
                            @if($sortField === 'full_name')
                                <span>{{ $sortDirection === 'asc' ? '↑' : '↓' }}</span>
                            @endif
                        </button>
                    </th>
                    <th>Chat ID</th>
                    <th>Plan</th>
                    <th>
                        <button wire:click="sortBy('subscribed_at')" class="flex items-center gap-1">
                            Subscribed
                            @if($sortField === 'subscribed_at')
                                <span>{{ $sortDirection === 'asc' ? '↑' : '↓' }}</span>
                            @endif
                        </button>
                    </th>
                    <th>Expires</th>
                    <th>Signals</th>
                    <th>Status</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                @forelse($subscribers as $sub)
                <tr>
                    <td>
                        <div class="font-semibold text-sm">{{ $sub->display_name }}</div>
                        @if($sub->username)
                            <div class="text-xs text-base-content/50">@{{ $sub->username }}</div>
                        @endif
                    </td>
                    <td class="font-mono text-xs text-base-content/60">{{ $sub->telegram_chat_id }}</td>
                    <td>
                        <span class="badge badge-sm {{ $sub->plan_badge }}">{{ $sub->plan }}</span>
                    </td>
                    <td class="text-xs text-base-content/60">
                        {{ $sub->subscribed_at?->format('d M Y') }}
                    </td>
                    <td class="text-xs {{ $sub->is_expired ? 'text-error' : 'text-base-content/60' }}">
                        {{ $sub->expires_at ? $sub->expires_at->format('d M Y') : '∞' }}
                        @if($sub->is_expired)
                            <span class="badge badge-error badge-xs ml-1">Expired</span>
                        @endif
                    </td>
                    <td class="text-center">{{ $sub->total_signals_received }}</td>
                    <td>
                        <span class="badge badge-sm {{ $sub->is_active ? 'badge-success' : 'badge-neutral' }}">
                            {{ $sub->is_active ? 'Active' : 'Inactive' }}
                        </span>
                    </td>
                    <td>
                        @if($sub->is_active)
                        <button wire:click="deactivate({{ $sub->id }})"
                                wire:confirm="Deactivate this subscriber?"
                                class="btn btn-ghost btn-xs text-error">
                            Deactivate
                        </button>
                        @else
                        <span class="text-xs text-base-content/30">—</span>
                        @endif
                    </td>
                </tr>
                @empty
                <tr>
                    <td colspan="8" class="text-center py-8 text-base-content/40">
                        No subscribers found.
                    </td>
                </tr>
                @endforelse
            </tbody>
        </table>
    </div>

    {{-- Pagination --}}
    <div>{{ $subscribers->links() }}</div>

</div>
