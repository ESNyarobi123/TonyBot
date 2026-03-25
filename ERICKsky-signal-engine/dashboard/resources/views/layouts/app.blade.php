<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'ERICKsky Signal Engine')</title>

    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📡</text></svg>">

    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.12.14/dist/full.min.css" rel="stylesheet" type="text/css" />
    <script src="https://cdn.tailwindcss.com"></script>

    <style>
        .page-transition { animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .nav-active { background: oklch(var(--p) / 0.15); color: oklch(var(--p)); border-right: 3px solid oklch(var(--p)); }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: oklch(var(--bc) / 0.2); border-radius: 3px; }
    </style>
</head>
<body class="min-h-screen bg-base-100">

    <div class="drawer lg:drawer-open">
        <input id="sidebar-toggle" type="checkbox" class="drawer-toggle" />

        <div class="drawer-content flex flex-col">

            <div class="navbar bg-base-200 lg:hidden sticky top-0 z-30 shadow-md">
                <div class="flex-none">
                    <label for="sidebar-toggle" class="btn btn-square btn-ghost">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                        </svg>
                    </label>
                </div>
                <div class="flex-1">
                    <span class="text-lg font-bold">📡 ERICKsky</span>
                </div>
            </div>

            <main class="flex-1 p-4 md:p-6 page-transition">
                @yield('content')
            </main>

            <footer class="footer footer-center p-4 bg-base-200 text-base-content/50 text-xs">
                <div>
                    <p>ERICKsky Signal Engine v1.0.0 — Institutional Grade Forex Signals</p>
                </div>
            </footer>
        </div>

        <div class="drawer-side z-40">
            <label for="sidebar-toggle" aria-label="close sidebar" class="drawer-overlay"></label>

            <aside class="w-64 min-h-screen bg-base-200 border-r border-base-300 flex flex-col">

                <div class="p-4 border-b border-base-300">
                    <a href="{{ route('dashboard') }}" class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-lg bg-primary flex items-center justify-center text-xl">
                            📡
                        </div>
                        <div>
                            <h1 class="text-lg font-bold leading-tight">ERICKsky</h1>
                            <p class="text-xs text-base-content/50">Signal Engine</p>
                        </div>
                    </a>
                </div>

                <nav class="flex-1 py-4">
                    <ul class="menu menu-md gap-1 px-2">

                        <li>
                            <a href="{{ route('dashboard') }}"
                               class="{{ request()->routeIs('dashboard') ? 'nav-active' : '' }}">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" /></svg>
                                Dashboard
                            </a>
                        </li>

                        <li>
                            <a href="{{ route('signals.index') }}"
                               class="{{ request()->routeIs('signals.*') ? 'nav-active' : '' }}">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
                                Signals
                            </a>
                        </li>

                        <li>
                            <a href="{{ route('subscribers.index') }}"
                               class="{{ request()->routeIs('subscribers.*') ? 'nav-active' : '' }}">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                Subscribers
                            </a>
                        </li>

                        <li>
                            <a href="{{ route('telegram.index') }}"
                               class="{{ request()->routeIs('telegram.*') ? 'nav-active' : '' }}">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
                                Telegram
                            </a>
                        </li>

                        <li>
                            <a href="{{ route('performance.index') }}"
                               class="{{ request()->routeIs('performance.*') ? 'nav-active' : '' }}">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                                Performance
                            </a>
                        </li>

                    </ul>
                </nav>

                <div class="p-4 border-t border-base-300">
                    <div class="flex items-center gap-2 text-sm">
                        <span class="w-2 h-2 rounded-full bg-success animate-pulse"></span>
                        <span class="font-semibold text-success">Bot Running</span>
                    </div>
                    <p class="text-xs text-base-content/40 mt-1">v1.0.0 • Institutional Grade</p>
                </div>

            </aside>
        </div>

    </div>

    @stack('scripts')

</body>
</html>