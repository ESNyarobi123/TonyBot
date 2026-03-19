<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (!Schema::hasTable('telegram_channels')) {
            Schema::create('telegram_channels', function (Blueprint $table) {
            $table->bigIncrements('id');
            $table->string('channel_name', 100);
            $table->string('chat_id', 50)->unique();
            $table->string('type', 20)->default('FREE');
            $table->boolean('is_active')->default(true);
            $table->integer('subscribers_count')->default(0);
            $table->timestampTz('created_at')->default(now());
            });
        }

        if (!Schema::hasTable('bot_state')) {
            Schema::create('bot_state', function (Blueprint $table) {
            $table->bigIncrements('id');
            $table->string('key', 50)->unique();
            $table->text('value')->nullable();
            $table->timestampTz('updated_at')->default(now());
            });
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('bot_state');
        Schema::dropIfExists('telegram_channels');
    }
};
