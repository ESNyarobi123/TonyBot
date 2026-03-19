<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (Schema::hasTable('subscribers')) {
            return;
        }

        Schema::create('subscribers', function (Blueprint $table) {
            $table->bigIncrements('id');
            $table->string('telegram_chat_id', 50)->unique();
            $table->string('username', 100)->nullable();
            $table->string('full_name', 200)->nullable();
            $table->string('plan', 20)->default('FREE');
            $table->timestampTz('subscribed_at')->default(now());
            $table->timestampTz('expires_at')->nullable();
            $table->boolean('is_active')->default(true);
            $table->integer('total_signals_received')->default(0);
            $table->timestampTz('created_at')->default(now());

            $table->index('telegram_chat_id');
            $table->index('plan');
            $table->index('is_active');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('subscribers');
    }
};
