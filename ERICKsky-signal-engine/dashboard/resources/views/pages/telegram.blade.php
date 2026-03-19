@extends('layouts.app')
@section('title', 'Telegram — ERICKsky Signal Engine')

@section('content')
<div class="space-y-6">

    <h1 class="text-2xl font-bold">Telegram Management</h1>

    {{-- Livewire Telegram Manager --}}
    @livewire('telegram-manager')

</div>
@endsection
