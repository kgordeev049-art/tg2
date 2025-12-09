# ... остальной код ...

async def notification_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки уведомлений"""
    query = update.callback_query
    await query.answer()
    
    text = "🔔 <b>Настройки уведомлений</b>\n\n"
    text += "Эта функция находится в разработке.\n"
    text += "В будущем здесь можно будет настроить получение уведомлений о новых скриптах и обновлениях."
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад в настройки", callback_data="settings")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    query = update.callback_query
    await query.answer()
    await admin_panel(update, context)
    return ConversationHandler.END

# ========== ДОБАВЛЯЕМ НЕДОСТАЮЩИЕ ФУНКЦИИ ИЗ ОРИГИНАЛЬНОГО КОДА ==========

async def add_script_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления скрипта"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'add_script'):
        await safe_edit_message(query, "❌ У вас нет прав для добавления скриптов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>📩 Отправьте содержимое скрипта:</b>", reply_markup=reply_markup)
    
    return ADD_SCRIPT

async def add_script_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение добавления скрипта"""
    script_content = update.message.text
    user_id = update.message.from_user.id
    
    token = generate_token()
    
    save_script_to_file(token, script_content, user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    bot_username = context.bot.username
    await update.message.reply_text(
        f"<b>✅ Скрипт добавлен!</b>\n\n"
        f"<b>Token:</b> <code>{token}</code>\n"
        f"<b>Ссылка:</b> <code>https://t.me/{bot_username}?start={token}</code>\n"
        f"<b>Сохранен в:</b> <code>scripts/{token}.json</code>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

async def delete_script_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления скрипта - запрос токена"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'delete_script'):
        await safe_edit_message(query, "❌ У вас нет прав для удаления скриптов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("📋 Показать все скрипты", callback_data="show_all_scripts")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>🗑 Введите токен скрипта для удаления:</b>", reply_markup=reply_markup)
    
    return DELETE_SCRIPT_INPUT

async def delete_script_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного токена для удаления"""
    token = update.message.text.strip().upper()
    
    script_data = load_script_from_file(token)
    
    if not script_data:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="delete_script")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Скрипт с токеном {token} не найден!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    if delete_script_file(token):
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ <b>Скрипт с токеном {token} успешно удален!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="delete_script")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Ошибка при удалении скрипта с токеном {token}!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    return ConversationHandler.END

async def show_all_scripts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все скрипты для удаления"""
    query = update.callback_query
    await query.answer()
    
    scripts = get_all_scripts()
    
    if not scripts:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message(query, "<b>❌ Нет доступных скриптов!</b>", reply_markup=reply_markup)
        return
    
    text = "<b>📋 Все скрипты:</b>\n\n"
    for i, (token, content, views) in enumerate(scripts, 1):
        preview = content[:30] + "..." if len(content) > 30 else content
        text += f"{i}. <code>{token}</code> | 👁 {views} | {preview}\n"
    
    keyboard = [
        [InlineKeyboardButton("🗑 Ввести токен для удаления", callback_data="delete_script")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления канала - шаг 1: ввод ID"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'add_channel'):
        await safe_edit_message(query, "❌ У вас нет прав для добавления каналов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>📢 Введите ID канала (например: -1001234567890):</b>", reply_markup=reply_markup)
    
    return ADD_CHANNEL_ID

async def add_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 2: ввод ссылки на канал"""
    channel_id = update.message.text.strip()
    
    try:
        await update.message.delete()
    except:
        pass
    
    context.user_data['channel_id'] = channel_id
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>🔗 Введите ссылку на канал:</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ADD_CHANNEL_LINK

async def add_channel_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение добавления канала"""
    channel_link = update.message.text.strip()
    user_id = update.message.from_user.id
    channel_id = context.user_data.get('channel_id')
    
    try:
        if channel_link.startswith('https://t.me/'):
            username = '@' + channel_link.split('/')[-1]
        elif channel_link.startswith('@'):
            username = channel_link
        else:
            username = '@' + channel_link
        
        real_subscribers = await get_real_channel_subscribers(context.bot, channel_id)
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Не удалось найти канал: {e}\n"
            "Убедитесь, что бот добавлен в канал как администратор!"
        )
        return ConversationHandler.END
    
    channel_data = {
        'channel_id': channel_id,
        'username': username,
        'invite_link': f"https://t.me/{username[1:]}",
        'initial_subscribers': real_subscribers,
        'current_subscribers': real_subscribers,
        'real_subscribers': real_subscribers,
        'added_by': user_id,
        'added_date': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }
    
    save_channel_to_file(channel_data)
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"<b>✅ ОП канал добавлен!</b>\n\n"
        f"<b>ID:</b> <code>{channel_id}</code>\n"
        f"<b>Ссылка:</b> <code>{username}</code>\n"
        f"<b>Текущее кол-во подписчиков:</b> <code>{real_subscribers}</code>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    context.user_data.pop('channel_id', None)
    
    return ConversationHandler.END

async def remove_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор канала для удаления"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'remove_channel'):
        await safe_edit_message(query, "❌ У вас нет прав для удаления каналов!")
        return
    
    channels = get_all_channels()
    
    if not channels:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message(query, "<b>❌ Нет добавленных каналов!</b>", reply_markup=reply_markup)
        return
    
    keyboard = []
    for channel_id, username, initial_subs, current_subs, real_subs in channels:
        display_subs = real_subs if real_subs > 0 else current_subs
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {username} | 👥 {display_subs} подписчиков",
                callback_data=f"rmch_{channel_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>🗑 Выберите канал для удаления:</b>", reply_markup=reply_markup)

async def remove_channel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление канала"""
    query = update.callback_query
    await query.answer()
    
    channel_id = query.data.replace("rmch_", "")
    
    if delete_channel_file(channel_id):
        await safe_edit_message(query, f"<b>✅ Канал удален!</b>")
    else:
        await safe_edit_message(query, f"<b>❌ Ошибка при удалении канала!</b>")
    
    await admin_panel(update, context)

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение списка каналов"""
    query = update.callback_query
    await query.answer()
    
    await update_all_channels_subscribers(context.bot)
    
    channels = get_all_channels()
    
    if not channels:
        text = "<b>🗒 Список каналов пуст!</b>"
    else:
        text = "<b>🗒 Список каналов:</b>\n\n"
        for i, (channel_id, username, initial_subs, current_subs, real_subs) in enumerate(channels, 1):
            display_subs = real_subs if real_subs > 0 else current_subs
            growth = display_subs - initial_subs
            growth_sign = "+" if growth >= 0 else ""
            text += f"{i}. {username}\n   ID: <code>{channel_id}</code>\n   Подписчиков: {display_subs}\n   Прирост: {growth_sign}{growth}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления администратора"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'add_admin'):
        await safe_edit_message(query, "❌ У вас нет прав для добавления администраторов!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>👤 Введите ID пользователя:</b>", reply_markup=reply_markup)
    
    return ADD_ADMIN

async def add_admin_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор прав для нового администратора"""
    try:
        new_admin_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!", parse_mode='HTML')
        return ConversationHandler.END
    
    if is_admin(new_admin_id):
        await update.message.reply_text("❌ Этот пользователь уже администратор!", parse_mode='HTML')
        return ConversationHandler.END
    
    context.user_data['new_admin_id'] = new_admin_id
    context.user_data['admin_permissions'] = ['view_stats']
    
    keyboard = []
    for perm_key, perm_name in PERMISSIONS.items():
        if perm_key == 'view_stats':
            keyboard.append([InlineKeyboardButton(f"✅ {perm_name}", callback_data=f"perm_{perm_key}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {perm_name}", callback_data=f"perm_{perm_key}")])
    
    keyboard.append([InlineKeyboardButton("💾 Сохранить", callback_data="save_admin")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"<b>🔧 Настройка прав для ID {new_admin_id}:</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return SET_ADMIN_RIGHTS

async def toggle_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение прав администратора"""
    query = update.callback_query
    await query.answer()
    
    perm_key = query.data.replace("perm_", "")
    new_admin_id = context.user_data.get('new_admin_id', 'N/A')
    
    if 'admin_permissions' not in context.user_data:
        context.user_data['admin_permissions'] = ['view_stats']
    
    current_perms = context.user_data['admin_permissions']
    
    if perm_key in current_perms:
        if perm_key != 'view_stats':
            current_perms.remove(perm_key)
    else:
        current_perms.append(perm_key)
    
    keyboard = []
    for p_key, p_name in PERMISSIONS.items():
        status = "✅" if p_key in current_perms else "❌"
        keyboard.append([InlineKeyboardButton(f"{status} {p_name}", callback_data=f"perm_{p_key}")])
    
    keyboard.append([InlineKeyboardButton("💾 Сохранить", callback_data="save_admin")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, f"<b>🔧 Настройка прав для ID {new_admin_id}:</b>", reply_markup=reply_markup)

async def save_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового администратора"""
    query = update.callback_query
    await query.answer()
    
    new_admin_id = context.user_data.get('new_admin_id')
    permissions = context.user_data.get('admin_permissions', ['view_stats'])
    
    if not new_admin_id:
        await safe_edit_message(query, "❌ Ошибка: ID не найден!")
        return ConversationHandler.END
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO admins (user_id, permissions, added_by) VALUES (?, ?, ?)',
            (new_admin_id, ','.join(permissions), query.from_user.id)
        )
        conn.commit()
    
    admin_cache[new_admin_id] = True
    
    context.user_data.pop('new_admin_id', None)
    context.user_data.pop('admin_permissions', None)
    
    await safe_edit_message(query, f"<b>✅ Администратор {new_admin_id} добавлен!</b>\n<b>Права:</b> {', '.join(permissions)}")
    await admin_panel(update, context)
    return ConversationHandler.END

async def remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор администратора для удаления"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'remove_admin'):
        await safe_edit_message(query, "❌ У вас нет прав для удаления администраторов!")
        return
    
    admins = get_all_admins()
    user_id = query.from_user.id
    
    keyboard = []
    for admin_id, permissions in admins:
        if admin_id != user_id and admin_id not in ADMIN_IDS:
            perm_count = "Все" if permissions == 'all' else str(len(permissions.split(',')))
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑 ID:{admin_id} | {perm_count} прав",
                    callback_data=f"rmadm_{admin_id}"
                )
            ])
    
    if not keyboard:
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        await safe_edit_message(query, "<b>❌ Нет администраторов для удаления!</b>", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>🗑 Выберите администратора:</b>", reply_markup=reply_markup)

async def remove_admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление администратора"""
    query = update.callback_query
    await query.answer()
    
    admin_id = int(query.data.replace("rmadm_", ""))
    
    if admin_id in ADMIN_IDS:
        await safe_edit_message(query, "<b>❌ Нельзя удалить главного администратора!</b>")
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
        conn.commit()
    
    admin_cache.pop(admin_id, None)
    
    await safe_edit_message(query, f"<b>✅ Администратор {admin_id} удален!</b>")
    await admin_panel(update, context)

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение списка администраторов"""
    query = update.callback_query
    await query.answer()
    
    admins = get_all_admins()
    
    main_admins = []
    other_admins = []
    
    for admin_id, permissions in admins:
        if permissions == 'all':
            main_admins.append(admin_id)
        else:
            other_admins.append(admin_id)
    
    text = "<b>📋 Список администраторов</b>\n\n"
    
    if main_admins:
        text += "<b>Главные админы</b>\n"
        for admin_id in main_admins:
            text += f"• {admin_id}\n"
        text += "\n"
    
    if other_admins:
        text += "<b>Доп. Администраторы</b>\n"
        for admin_id in other_admins:
            text += f"• {admin_id}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню статистики"""
    query = update.callback_query
    await query.answer()
    
    text = "<b>📊 Статистика</b>"
    
    keyboard = [
        [InlineKeyboardButton("📢 Каналы", callback_data="stats_channels")],
        [InlineKeyboardButton("📦 Скрипты", callback_data="stats_scripts")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="users_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def stats_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика каналов - запрос ID"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>📢 Введите ID канала для просмотра статистики:</b>", reply_markup=reply_markup)
    
    return VIEW_CHANNEL_STATS

async def stats_channels_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ID канала для статистики"""
    channel_id = update.message.text.strip()
    
    channel_data = load_channel_from_file(channel_id)
    
    if not channel_data:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="stats_channels")],
            [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Канал с ID {channel_id} не найден!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    try:
        real_subscribers = await get_real_channel_subscribers(context.bot, channel_id)
        channel_data['real_subscribers'] = real_subscribers
        channel_data['current_subscribers'] = real_subscribers
        save_channel_to_file(channel_data)
    except:
        real_subscribers = channel_data.get('real_subscribers', 0)
    
    initial_subs = channel_data.get('initial_subscribers', 0)
    growth = real_subscribers - initial_subs
    growth_sign = "+" if growth >= 0 else ""
    
    text = f"""<b>📊 Статистика канала</b>

<b>ID:</b> <code>{channel_data['channel_id']}</code>
<b>Ссылка:</b> {channel_data['username']}
<b>Пригласительная ссылка:</b> {channel_data.get('invite_link', 'Нет')}

<b>📈 Статистика подписчиков:</b>
• Начальное количество: {initial_subs}
• Текущее количество: {real_subscribers}
• Прирост: {growth_sign}{growth}

<b>📅 Информация:</b>
• Добавлен: {channel_data.get('added_date', 'Неизвестно')}
• Добавил: {channel_data.get('added_by', 'Неизвестно')}
• Последнее обновление: {channel_data.get('last_updated', 'Никогда')}"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    return ConversationHandler.END

async def stats_scripts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика скриптов - запрос токена"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "<b>📦 Введите токен скрипта для просмотра статистики:</b>", reply_markup=reply_markup)
    
    return VIEW_SCRIPT_STATS

async def stats_scripts_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода токена скрипта для статистики"""
    token = update.message.text.strip().upper()
    
    script_data = load_script_from_file(token)
    
    if not script_data:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="stats_scripts")],
            [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ <b>Скрипт с токеном {token} не найден!</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    views = script_data.get('views', 0)
    created_date = script_data.get('created_date', 'Неизвестно')
    created_by = script_data.get('created_by', 'Неизвестно')
    
    try:
        created_date_obj = datetime.fromisoformat(created_date)
        created_date_formatted = created_date_obj.strftime("%d.%m.%Y %H:%M")
    except:
        created_date_formatted = created_date
    
    text = f"""<b>📊 Статистика скрипта</b>

<b>Токен:</b> <code>{token}</code>
<b>👁 Количество переходов:</b> <b>{views}</b>

<b>📅 Информация:</b>
• Создан: {created_date_formatted}
• Создал: {created_by}

<b>🔗 Ссылка для доступа:</b>
<code>https://t.me/{context.bot.username}?start={token}</code>"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="view_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    return ConversationHandler.END

# ========== ФУНКЦИИ РАССЫЛКИ ==========

async def broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню рассылки"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'broadcast'):
        await safe_edit_message(query, "❌ У вас нет прав для рассылки!")
        return
    
    user_count = get_user_count()
    
    keyboard = [
        [InlineKeyboardButton("📝 Текстовая рассылка", callback_data="broadcast_text")],
        [InlineKeyboardButton("🖼 Рассылка с фото", callback_data="broadcast_photo")],
        [InlineKeyboardButton("📊 Статистика пользователей", callback_data="users_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"<b>📢 Меню рассылки</b>\n\n"
    text += f"<b>👥 Всего пользователей в базе:</b> <code>{user_count}</code>\n"
    text += f"<b>📊 Охват аудитории:</b> <code>{user_count}</code> пользователей\n\n"
    text += "<b>Выберите тип рассылки:</b>"
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def users_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика пользователей"""
    query = update.callback_query
    await query.answer()
    
    users = get_all_users()
    user_count = len(users)
    
    text = f"<b>📊 Статистика пользователей</b>\n\n"
    text += f"<b>👥 Всего пользователей:</b> <code>{user_count}</code>\n\n"
    
    if user_count > 0:
        text += "<b>Последние 10 пользователей:</b>\n"
        for i, user in enumerate(users[:10], 1):
            user_id, username, first_name, last_name = user
            username_display = f"@{username}" if username else "Без username"
            name = f"{first_name} {last_name}".strip() if last_name else first_name
            text += f"{i}. {name} ({username_display}) - ID: <code>{user_id}</code>\n"
    
    if user_count > 10:
        text += f"\n<i>... и еще {user_count - 10} пользователей</i>"
    
    keyboard = [
        [InlineKeyboardButton("📢 Начать рассылку", callback_data="broadcast_menu")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, text, reply_markup=reply_markup)

async def broadcast_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало текстовой рассылки"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'broadcast'):
        await safe_edit_message(query, "❌ У вас нет прав для рассылки!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_count = get_user_count()
    
    text = f"<b>📝 Текстовая рассылка</b>\n\n"
    text += f"<b>👥 Будет отправлено:</b> <code>{user_count}</code> пользователям\n\n"
    text += "<b>Введите текст для рассылки:</b>\n"
    text += "<i>Поддерживается HTML разметка</i>"
    
    await safe_edit_message(query, text, reply_markup=reply_markup)
    
    return BROADCAST_INPUT_TEXT

async def broadcast_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало рассылки с фото"""
    query = update.callback_query
    await query.answer()
    
    if not has_permission(query.from_user.id, 'broadcast'):
        await safe_edit_message(query, "❌ У вас нет прав для рассылки!")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_count = get_user_count()
    
    text = f"<b>🖼 Рассылка с фото</b>\n\n"
    text += f"<b>👥 Будет отправлено:</b> <code>{user_count}</code> пользователям\n\n"
    text += "<b>Отправьте фото для рассылки:</b>\n"
    text += "<i>Можно отправить как файл или фотографию</i>"
    
    await safe_edit_message(query, text, reply_markup=reply_markup)
    
    return BROADCAST_INPUT_PHOTO

async def broadcast_input_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного текста для рассылки"""
    text = update.message.text
    context.user_data['broadcast_text'] = text
    
    user_count = get_user_count()
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать рассылку", callback_data="start_broadcast_text")],
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    preview_text = f"<b>📝 Предпросмотр рассылки</b>\n\n"
    preview_text += f"<b>👥 Кому:</b> <code>{user_count}</code> пользователям\n\n"
    preview_text += f"<b>📄 Текст:</b>\n{text}\n\n"
    preview_text += f"<b>📏 Длина текста:</b> <code>{len(text)}</code> символов\n\n"
    preview_text += "<b>Начать рассылку?</b>"
    
    await update.message.reply_text(preview_text, reply_markup=reply_markup, parse_mode='HTML')
    
    return BROADCAST_CONFIRM

async def broadcast_input_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка полученного фото для рассылки"""
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        context.user_data['broadcast_photo'] = photo_file.file_id
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        photo_file = await update.message.document.get_file()
        context.user_data['broadcast_photo'] = photo_file.file_id
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте изображение!")
        return BROADCAST_INPUT_PHOTO
    
    keyboard = [
        [InlineKeyboardButton("➡️ Далее: ввод текста", callback_data="input_photo_caption")],
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Фото получено! Теперь введите текст для рассылки:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return BROADCAST_INPUT_TEXT

async def broadcast_input_photo_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод текста для фото-рассылки"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(query, "📝 Введите текст для рассылки с фото:", reply_markup=reply_markup)
    
    return BROADCAST_INPUT_TEXT

async def broadcast_confirm_photo_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение фото-рассылки с текстом"""
    text = update.message.text
    context.user_data['broadcast_text'] = text
    
    user_count = get_user_count()
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать рассылку", callback_data="start_broadcast_photo")],
        [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    preview_text = f"<b>🖼 Предпросмотр рассылки с фото</b>\n\n"
    preview_text += f"<b>👥 Кому:</b> <code>{user_count}</code> пользователям\n\n"
    preview_text += f"<b>📄 Текст:</b>\n{text}\n\n"
    preview_text += f"<b>📏 Длина текста:</b> <code>{len(text)}</code> символов\n\n"
    preview_text += "<b>Начать рассылку?</b>"
    
    await update.message.reply_text(preview_text, reply_markup=reply_markup, parse_mode='HTML')
    
    return BROADCAST_CONFIRM

async def start_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск текстовой рассылки"""
    query = update.callback_query
    await query.answer()
    
    text = context.user_data.get('broadcast_text', '')
    
    if not text:
        await safe_edit_message(query, "❌ Текст для рассылки не найден!")
        return ConversationHandler.END
    
    users = get_all_users()
    total_users = len(users)
    
    if total_users == 0:
        await safe_edit_message(query, "❌ Нет пользователей для рассылки!")
        return ConversationHandler.END
    
    progress_msg = await query.message.reply_text(
        f"🔄 <b>Начинаю рассылку...</b>\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"✅ Отправлено: <code>0</code>\n"
        f"❌ Ошибок: <code>0</code>\n"
        f"📊 Прогресс: <code>0%</code>",
        parse_mode='HTML'
    )
    
    success = 0
    failed = 0
    start_time = datetime.now()
    
    for i, user in enumerate(users, 1):
        user_id = user[0]
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='HTML'
            )
            success += 1
            
            if i % 10 == 0 or i == total_users:
                progress = int((i / total_users) * 100)
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = i / elapsed if elapsed > 0 else 0
                
                await progress_msg.edit_text(
                    f"🔄 <b>Рассылка в процессе...</b>\n"
                    f"👥 Всего пользователей: <code>{total_users}</code>\n"
                    f"✅ Отправлено: <code>{success}</code>\n"
                    f"❌ Ошибок: <code>{failed}</code>\n"
                    f"📊 Прогресс: <code>{progress}%</code> ({i}/{total_users})\n"
                    f"⚡ Скорость: <code>{speed:.1f}</code> сообщ./сек",
                    parse_mode='HTML'
                )
            
            await asyncio.sleep(0.05)
            
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
            
            if failed % 5 == 0:
                progress = int((i / total_users) * 100)
                await progress_msg.edit_text(
                    f"🔄 <b>Рассылка в процессе...</b>\n"
                    f"👥 Всего пользователей: <code>{total_users}</code>\n"
                    f"✅ Отправлено: <code>{success}</code>\n"
                    f"❌ Ошибок: <code>{failed}</code>\n"
                    f"📊 Прогресс: <code>{progress}%</code>",
                    parse_mode='HTML'
                )
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    await progress_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"✅ Успешно отправлено: <code>{success}</code>\n"
        f"❌ Ошибок: <code>{failed}</code>\n"
        f"📊 Охват: <code>{(success/total_users*100):.1f}%</code>\n"
        f"⏱ Время: <code>{total_time:.1f}</code> секунд\n"
        f"⚡ Средняя скорость: <code>{(total_users/total_time):.1f}</code> сообщ./сек",
        parse_mode='HTML'
    )
    
    context.user_data.pop('broadcast_text', None)
    
    keyboard = [
        [InlineKeyboardButton("📢 Новая рассылка", callback_data="broadcast_menu")],
        [InlineKeyboardButton("🔙 В админ панель", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "✅ Рассылка завершена!",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

async def start_broadcast_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск рассылки с фото"""
    query = update.callback_query
    await query.answer()
    
    photo_id = context.user_data.get('broadcast_photo')
    text = context.user_data.get('broadcast_text', '')
    
    if not photo_id or not text:
        await safe_edit_message(query, "❌ Данные для рассылки неполные!")
        return ConversationHandler.END
    
    users = get_all_users()
    total_users = len(users)
    
    if total_users == 0:
        await safe_edit_message(query, "❌ Нет пользователей для рассылки!")
        return ConversationHandler.END
    
    progress_msg = await query.message.reply_text(
        f"🔄 <b>Начинаю рассылку с фото...</b>\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"✅ Отправлено: <code>0</code>\n"
        f"❌ Ошибок: <code>0</code>\n"
        f"📊 Прогресс: <code>0%</code>",
        parse_mode='HTML'
    )
    
    success = 0
    failed = 0
    start_time = datetime.now()
    
    for i, user in enumerate(users, 1):
        user_id = user[0]
        
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=text,
                parse_mode='HTML'
            )
            success += 1
            
            if i % 10 == 0 or i == total_users:
                progress = int((i / total_users) * 100)
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = i / elapsed if elapsed > 0 else 0
                
                await progress_msg.edit_text(
                    f"🔄 <b>Рассылка в процессе...</b>\n"
                    f"👥 Всего пользователей: <code>{total_users}</code>\n"
                    f"✅ Отправлено: <code>{success}</code>\n"
                    f"❌ Ошибок: <code>{failed}</code>\n"
                    f"📊 Прогресс: <code>{progress}%</code> ({i}/{total_users})\n"
                    f"⚡ Скорость: <code>{speed:.1f}</code> сообщ./сек",
                    parse_mode='HTML'
                )
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки фото пользователю {user_id}: {e}")
            
            if failed % 5 == 0:
                progress = int((i / total_users) * 100)
                await progress_msg.edit_text(
                    f"🔄 <b>Рассылка в процессе...</b>\n"
                    f"👥 Всего пользователей: <code>{total_users}</code>\n"
                    f"✅ Отправлено: <code>{success}</code>\n"
                    f"❌ Ошибок: <code>{failed}</code>\n"
                    f"📊 Прогресс: <code>{progress}%</code>",
                    parse_mode='HTML'
                )
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    await progress_msg.edit_text(
        f"✅ <b>Рассылка с фото завершена!</b>\n\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"✅ Успешно отправлено: <code>{success}</code>\n"
        f"❌ Ошибок: <code>{failed}</code>\n"
        f"📊 Охват: <code>{(success/total_users*100):.1f}%</code>\n"
        f"⏱ Время: <code>{total_time:.1f}</code> секунд\n"
        f"⚡ Средняя скорость: <code>{(total_users/total_time):.1f}</code> сообщ./сек",
        parse_mode='HTML'
    )
    
    context.user_data.pop('broadcast_photo', None)
    context.user_data.pop('broadcast_text', None)
    
    keyboard = [
        [InlineKeyboardButton("📢 Новая рассылка", callback_data="broadcast_menu")],
        [InlineKeyboardButton("🔙 В админ панель", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "✅ Рассылка с фото завершена!",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    return ConversationHandler.END

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена рассылки"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop('broadcast_text', None)
    context.user_data.pop('broadcast_photo', None)
    
    await broadcast_menu(update, context)
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    
    if isinstance(context.error, Conflict):
        logger.error("⚠️ Обнаружен конфликт: другой экземпляр бота уже запущен!")
        logger.error("🛑 Остановите все другие экземпляры бота и перезапустите этот")

# ========== ЗАПУСК БОТА ==========
def main():
    """Главная функция"""
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("PanelAdmin", panel_admin))
    
    # Обработчик для создания ссылки
    create_link_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_link_start, pattern="^create_link$")],
        states={
            CREATE_LINK_CONTENT: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                    create_link_content
                )
            ],
            CREATE_LINK_BUTTON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_link_button)
            ],
        },
        fallbacks=[
            CommandHandler("skip", create_link_button),
            CallbackQueryHandler(cancel, pattern="^admin_panel$")
        ],
        per_message=False
    )
    
    # Обработчик для поиска скриптов
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_scripts_start, pattern="^search_scripts$")],
        states={
            SEARCH_SCRIPTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_scripts_process)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^back_to_start$")
        ],
        per_message=False
    )
    
    # Добавляем ConversationHandler для админских функций
    add_script_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_script_start, pattern="^add_script$")],
        states={
            ADD_SCRIPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_script_finish)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^admin_panel$")],
        per_message=False
    )
    
    add_channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_channel_start, pattern="^add_channel$")],
        states={
            ADD_CHANNEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_id)],
            ADD_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_finish)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^admin_panel$")],
        per_message=False
    )
    
    add_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_admin_start, pattern="^add_admin$")],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_finish)],
            SET_ADMIN_RIGHTS: [CallbackQueryHandler(toggle_permission, pattern="^perm_")]
        },
        fallbacks=[
            CallbackQueryHandler(save_admin, pattern="^save_admin$"),
            CallbackQueryHandler(cancel, pattern="^admin_panel$")
        ],
        per_message=False
    )
    
    delete_script_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_script_start, pattern="^delete_script$")],
        states={
            DELETE_SCRIPT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_script_input)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^admin_panel$"),
            CallbackQueryHandler(show_all_scripts, pattern="^show_all_scripts$")
        ],
        per_message=False
    )
    
    stats_channels_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(stats_channels, pattern="^stats_channels$")],
        states={
            VIEW_CHANNEL_STATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, stats_channels_input)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^admin_panel$")
        ],
        per_message=False
    )
    
    stats_scripts_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(stats_scripts, pattern="^stats_scripts$")],
        states={
            VIEW_SCRIPT_STATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, stats_scripts_input)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^admin_panel$")
        ],
        per_message=False
    )
    
    # Добавляем ConversationHandler для рассылки
    broadcast_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_text_start, pattern="^broadcast_text$")],
        states={
            BROADCAST_INPUT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_input_text)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(start_broadcast_text, pattern="^start_broadcast_text$"),
                               CallbackQueryHandler(cancel_broadcast, pattern="^broadcast_menu$")]
        },
        fallbacks=[CallbackQueryHandler(cancel_broadcast, pattern="^broadcast_menu$")],
        per_message=False
    )
    
    broadcast_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_photo_start, pattern="^broadcast_photo$")],
        states={
            BROADCAST_INPUT_PHOTO: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, broadcast_input_photo)],
            BROADCAST_INPUT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_confirm_photo_text)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(start_broadcast_photo, pattern="^start_broadcast_photo$"),
                               CallbackQueryHandler(cancel_broadcast, pattern="^broadcast_menu$")]
        },
        fallbacks=[
            CallbackQueryHandler(broadcast_input_photo_caption, pattern="^input_photo_caption$"),
            CallbackQueryHandler(cancel_broadcast, pattern="^broadcast_menu$")
        ],
        per_message=False
    )
    
    # Регистрируем все обработчики
    application.add_handler(create_link_conv)
    application.add_handler(search_conv)
    application.add_handler(add_script_conv)
    application.add_handler(add_channel_conv)
    application.add_handler(add_admin_conv)
    application.add_handler(delete_script_conv)
    application.add_handler(stats_channels_conv)
    application.add_handler(stats_scripts_conv)
    application.add_handler(broadcast_text_conv)
    application.add_handler(broadcast_photo_conv)
    
    # Добавляем обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    application.add_error_handler(error_handler)
    
    logger.info("🚀 Бот BAFScripts запущен и готов к работе!")
    logger.info(f"📁 Скрипты сохраняются в: {SCRIPTS_DIR}")
    logger.info(f"📁 Каналы сохраняются в: {CHANNELS_DIR}")
    logger.info(f"📁 Ссылки сохраняются в: {LINKS_DIR}")
    logger.info(f"📸 Изображение приветствия: {WELCOME_IMAGE_PATH}")
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Conflict:
        logger.error("❌ Конфликт: другой экземпляр бота уже запущен!")
        logger.error("💡 Остановите все другие экземпляры и перезапустите бота")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")

if __name__ == '__main__':
    main()
