@extends('layouts.app')
@section('title', 'Subscribers — ERICKsky Signal Engine')

@section('content')
<div class="space-y-6">

    <div class="flex items-center justify-between flex-wrap gap-3">
        <h1 class="text-2xl font-bold">Subscribers</h1>
        <button onclick="document.getElementById('add-modal').showModal()" class="btn btn-primary btn-sm gap-2">
            + Add Subscriber
        </button>
    </div>

    {{-- Stats Row --}}
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        @php
            $total   = $subscribers->total();
            $premium = \App\Models\Subscriber::premium()->count();
            $free    = \App\Models\Subscriber::active()->where('plan','FREE')->count();
            $inactive = \App\Models\Subscriber::where('is_active', false)->count();
        @endphp
        <div class="stat bg-base-200 rounded-xl p-4">
            <div class="stat-title text-xs">Total Active</div>
            <div class="stat-value text-2xl text-primary">{{ \App\Models\Subscriber::active()->count() }}</div>
        </div>
        <div class="stat bg-base-200 rounded-xl p-4">
            <div class="stat-title text-xs">Premium</div>
            <div class="stat-value text-2xl text-warning">{{ $premium }}</div>
        </div>
        <div class="stat bg-base-200 rounded-xl p-4">
            <div class="stat-title text-xs">Free</div>
            <div class="stat-value text-2xl">{{ $free }}</div>
        </div>
        <div class="stat bg-base-200 rounded-xl p-4">
            <div class="stat-title text-xs">Inactive</div>
            <div class="stat-value text-2xl text-base-content/40">{{ $inactive }}</div>
        </div>
    </div>

    {{-- Livewire Table --}}
    @livewire('subscriber-table')

</div>

{{-- Add Subscriber Modal --}}
<dialog id="add-modal" class="modal">
    <div class="modal-box">
        <h3 class="font-bold text-lg mb-4">Add New Subscriber</h3>
        <form method="POST" action="{{ route('subscribers.store') }}" class="space-y-4">
            @csrf
            <div class="form-control">
                <label class="label"><span class="label-text">Telegram Chat ID *</span></label>
                <input type="text" name="telegram_chat_id" required class="input input-bordered" placeholder="-100xxxxxxxxx">
            </div>
            <div class="form-control">
                <label class="label"><span class="label-text">Username</span></label>
                <input type="text" name="username" class="input input-bordered" placeholder="@username">
            </div>
            <div class="form-control">
                <label class="label"><span class="label-text">Full Name</span></label>
                <input type="text" name="full_name" class="input input-bordered">
            </div>
            <div class="form-control">
                <label class="label"><span class="label-text">Plan *</span></label>
                <select name="plan" class="select select-bordered" required>
                    <option value="FREE">Free</option>
                    <option value="BASIC">Basic</option>
                    <option value="PREMIUM">Premium</option>
                </select>
            </div>
            <div class="form-control">
                <label class="label"><span class="label-text">Expires At</span></label>
                <input type="date" name="expires_at" class="input input-bordered">
            </div>
            <div class="modal-action">
                <button type="submit" class="btn btn-primary">Add Subscriber</button>
                <button type="button" onclick="document.getElementById('add-modal').close()" class="btn btn-ghost">Cancel</button>
            </div>
        </form>
    </div>
    <form method="dialog" class="modal-backdrop"><button>close</button></form>
</dialog>
@endsection
