import requests
import telebot
import re
from telebot import types
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import calendar
import pymorphy2
import psycopg2
import pickle
from data_preparation import clean_sentences
import nltk
import time

# TODO переделать подписи на диаграмме (если категорий > 4, то вынести подписи за рамки диаграммы)
# TODO продумать ситуацию с экстренным отключением БД и использовать error_message
# TODO сделать оформление функций и документирование проекта для будущей заливки на git

""" Here are some typical responds on different kinds of topics. The actual respond will be generated
 by np.random.randint() function """

WRONG_COMMAND_RESPONSES = ['Не понял. ', 'Не могу найти такой команды. ', 'Не понял тебя. ',
                           'Кажется, такой команды не существует... ', 'Прости, не понимаю тебя. ']

PRE_GOAL_SETTING_RESPONSES = ['О, новая цель! Прекрасно! ', 'Цели - это то, что помогает нам двигаться вперед! ',
                              'Круто! Новая цель! Так держать! ', 'Отлично, цели - это всегда классно! ']

GOAL_EXAMPLES = ['Новый автомобиль', 'Новая квартира', 'Новый смартфон', 'Новый iPhone',
                 'Курс по программированию на Coursera', 'Путешествие на мальдивы']

EXPANSES_EXAMPLES = ['Покушал в ресторане на 1900 рублей', 'Сходил на примем к врачу за 1000 рублей',
                     'Купил продуктов в магазине на 2000 рублей', 'Авиабилеты за 10000 рублей',
                     'Установил газовую плиту в дом за 5000 рублей']

SUCCESSFUL_RESPONSES = ['Принято! ', 'Понял! ', 'Запомнил! ', 'Отлично! ']

COMPLIMENT_RESPONDS = ['Отличная работа! ', 'Круто! ', 'Все круто! ', 'Отличная новость! ', 'Неплохо! ']

CHEER_UP_RESPONDS = ['Хм... Кажется, все еще не так плохо! ', 'Все почти получилось! ', 'Нужно чуть-чуть поднажать. ']

EXIT_RESPONDS = ['Принято! Выхожу.', 'Понял, отбой!', 'Как скажете, выхожу!']

MODEL_CATEGORIES = ['ЖКХ', 'РАЗВЛЕЧЕНИЯ', 'ПИТАНИЕ', 'ЗДОРОВЬЕ', 'ТРАНСПОРТ']

bot = telebot.TeleBot(token="1287334655:AAFhe8mO_1vi1QnaZgXfSQ_0gC_slrrTjOg")

SECS_BEFORE_RECONNECT = 3  # time in secs before reconnect

# PostgreSQL database configuration
database = "postgres"
user = "postgres"
password = "postgres"
host = "127.0.0.1"
port = "5432"

""" Meeting part. In this part a bot will ask some information from a user and put it in the variables above """


@bot.message_handler(content_types=['text'], commands=['start'])
def start_message(message):
    if not is_person_registered(message.chat.id):
        msg = bot.send_message(message.chat.id, 'Привет! Я твой личный финансовый бот, '
                                                'который поможет тебе вести статистику расходов '
                                                'и иметь к ней доступ отовсюду! Для начала, давай '
                                                'познакомимся Я - KeeperBot, а как твое имя?')
        bot.register_next_step_handler(msg, ask_name)
    else:
        bot.send_message(message.chat.id, 'Вы уже зарегистрированы. Используйте /help для просмотра списка команд.')


user_name = ''  # person's name


def ask_name(message):
    # if a user typed in the command by mistake
    if is_person_registered(message.chat.id) and message.text == '/exit':
        bot.send_message(message.chat.id, EXIT_RESPONDS[np.random.randint(0, len(EXIT_RESPONDS))])
        return

    global user_name
    user_name = message.text
    if '\s' in user_name or user_name == '':
        msg = bot.send_message(message.chat.id, 'Имя не должно быть пустым или содержать пробельные символы. '
                                                'Пожалуйста, введите имя ещё раз.')
        bot.register_next_step_handler(msg, ask_name)
    elif re.search(r'\d', user_name):
        msg = bot.send_message(message.chat.id, 'Имя не может содержать цифры. Пожалуйста, введите имя ещё раз.')
        bot.register_next_step_handler(msg, ask_name)
    elif not re.search(r'^[А-ЯA-Z]', user_name):
        msg = bot.send_message(message.chat.id, 'Имя должно начинаться с заглавной буквы. '
                                                'Пожалуйста, введите имя ещё раз.')
        bot.register_next_step_handler(msg, ask_name)
    elif re.search(r'[\W]', user_name):
        msg = bot.send_message(message.chat.id, 'Имя не должно содержать символов, отличных от букв. '
                                                'Пожалуйста, введите имя еще раз.')
        bot.register_next_step_handler(msg, ask_name)
    elif len(user_name) > 30:
        msg = bot.send_message(message.chat.id, 'Имя не может содержать более 30 символов. '
                                                'Пожалуйста, введите имя еще раз.')
        bot.register_next_step_handler(msg, ask_name)
    else:
        # name meets all the requirements
        if not is_person_registered(message.chat.id):
            bot.send_message(message.chat.id, f'Приятно познакомиться, *{user_name}*!', parse_mode='markdown')
            # now we're asking a person to enter an average income
            bot.send_message(message.chat.id, 'Отлично! Теперь введи, пожалуйста, свой среднемесячный доход, чтобы я '
                                              'смог помочь тебе с твоими финансами (введи сумму в рублях).')
            bot.register_next_step_handler(message, ask_income)
        else:
            update_db(message.chat.id, 'bot_user', {'name': user_name})
            bot.send_message(message.chat.id, f'Имя изменено на "*{user_name}*"', parse_mode='markdown')


def ask_income(message):
    # if a user typed in the command by mistake
    if is_person_registered(message.chat.id) and message.text == '/exit':
        bot.send_message(message.chat.id, EXIT_RESPONDS[np.random.randint(0, len(EXIT_RESPONDS))])
        return

    income_str = message.text
    if not income_str.isdigit():
        msg = bot.send_message(message.chat.id, 'Число введено некорректно. Пожалуйста, введите ваш '
                                                'доход еще раз.')
        bot.register_next_step_handler(msg, ask_income)
    else:
        income = int(income_str)
        if income <= 0:
            msg = bot.send_message(message.chat.id, 'Доход не может быть отрицательным или равен нулю! Пожалуйста, '
                                                    'введите ваш доход еще раз')
            bot.register_next_step_handler(msg, ask_income)
        else:
            if not is_person_registered(message.chat.id):
                add_user_to_db(message.chat.id, user_name, income)
                msg = bot.send_message(message.chat.id,
                                       SUCCESSFUL_RESPONSES[np.random.randint(0, len(SUCCESSFUL_RESPONSES))] +
                                       'Теперь позволь мне рассказать, что я могу.')
                print_commands(msg)
                bot.send_message(msg.chat.id, 'Ты можешь ввести одну из комманд и далее следовать инструкциям.')
            else:
                update_db(message.chat.id, 'bot_user', {'income': income})
                bot.send_message(message.chat.id,
                                 SUCCESSFUL_RESPONSES[np.random.randint(0, len(SUCCESSFUL_RESPONSES))] +
                                 f"Теперь ваш доход составляет *{income}* {get_correct_form(income, word='рубль')}.",
                                 parse_mode='markdown')


""" It this part of the code the functions that execute each command from the list of commands are defined """


@bot.message_handler(content_types=['text'], commands=['help'])
def print_commands(message):
    if is_person_registered(message.chat.id):
        bot.send_message(message.chat.id, 'Вот список команд:\n'
                                          '/help - показать список команд\n'
                                          '/changename - изменить имя\n'
                                          '/setincome - установить среднемесячный доход\n'
                                          '/addgoal - установить финансовую цель (укажите финансовую '
                                          'цель, количество средств, необходимых для ее достижения и время, за которое '
                                          'вы планируете ее достичь)\n'
                                          '/goals - вывести список целей\n'
                                          '/delgoal - удалить цель\n'
                                          '/setregexp - установить регулярные месячные траты (regular expenses)\n'
                                          '/add – добавить трату\n'
                                          '/delete - удалить последнюю трату\n'
                                          '/details  – вывести диаграмму расходов за месяц по следующим статьям:\n'
                                          '\t - ЖКХ\n'
                                          '\t – питание\n'
                                          '\t – транспорт\n'
                                          '\t – здоровье\n'
                                          '\t – развлечения\n'
                                          '\t – другое\n'
                                          '/advice – бот комментирует динамику по расходам и дает советы по процессу '
                                          'достижения финансовых целей\n'
                                          '/exit - выход из команды (если команда была выбрана ошибочно)',
                         parse_mode='markdown')
    else:
        bot.register_next_step_handler(message, start_message)


@bot.message_handler(content_types=['text'], commands=['changename'])
def change_name(message):
    if is_person_registered(message.chat.id):
        msg = bot.send_message(message.chat.id, 'Пожалуйста, введите новое имя.')
        bot.register_next_step_handler(msg, ask_name)
    else:
        bot.register_next_step_handler(message, start_message)


@bot.message_handler(content_types=['text'], commands=['setincome'])
def set_income(message):
    if is_person_registered(message.chat.id):
        msg = bot.send_message(message.chat.id, 'Пожалуйста, введите ваш новый доход.')
        bot.register_next_step_handler(msg, ask_income)
    else:
        bot.register_next_step_handler(message, start_message)


@bot.message_handler(content_types=['text'], commands=['addgoal'])
def set_goal(message):
    if is_person_registered(message.chat.id):
        msg = bot.send_message(message.chat.id, PRE_GOAL_SETTING_RESPONSES[np.random.randint(
            0, len(PRE_GOAL_SETTING_RESPONSES))] + 'Пожалуйста, введите название вашей цели (например, \"'
                               + GOAL_EXAMPLES[np.random.randint(0, len(GOAL_EXAMPLES))] + '\").')
        bot.register_next_step_handler(msg, ask_goal_name)
    else:
        bot.register_next_step_handler(message, start_message)


current_goal = {}


def ask_goal_name(message):
    # if a user typed in the command by mistake
    if is_person_registered(message.chat.id) and message.text == '/exit':
        bot.send_message(message.chat.id, EXIT_RESPONDS[np.random.randint(0, len(EXIT_RESPONDS))])
        return

    goal_name = message.text
    goals = get_goals_from_db(message.chat.id)
    # if the goal is in goals dictionary already, just skip it
    if goal_name not in [goals[i][0] for i in range(len(goals))]:
        money_markup = types.ReplyKeyboardMarkup(row_width=3, one_time_keyboard=True)
        money_markup.add('5000', '10000', '15000')
        money_markup.add('30000', '50000', '70000')
        money_markup.add('100000', '250000', '500000')

        current_goal['name'] = goal_name

        msg = bot.send_message(message.chat.id, SUCCESSFUL_RESPONSES[np.random.randint(0, len(SUCCESSFUL_RESPONSES))] +
                               'Теперь укажите количество денежных средств, необходимых для '
                               'достижения введенной финансовой цели или выбирете один из вариантов в меню.',
                               reply_markup=money_markup)

        bot.register_next_step_handler(msg, ask_goal_money)
    else:
        bot.send_message(message.chat.id, f'Цель \"*{goal_name}*\" уже находится в вашем списке целей.',
                         parse_mode='markdown')


def ask_goal_money(message):
    if is_person_registered(message.chat.id) and message.text == '/exit':
        bot.send_message(message.chat.id, EXIT_RESPONDS[np.random.randint(0, len(EXIT_RESPONDS))])
        return

    amount_str = message.text
    if not amount_str.isdigit():
        msg = bot.send_message(message.chat.id, 'Сумма введена некорректно. Пожалуйста, введите сумму еще раз.')
        bot.register_next_step_handler(msg, ask_goal_money)
    else:
        time_markup = types.ReplyKeyboardMarkup(row_width=3, one_time_keyboard=True)
        time_markup.add('1 неделя', '2 недели', '6 недель')
        time_markup.add('1 месяц', '2 месяца', '6 месяцев')
        time_markup.add('12 месяцев', '18 месяцев', '24 месяца')

        current_goal['amount'] = int(amount_str)
        msg = bot.send_message(message.chat.id, SUCCESSFUL_RESPONSES[np.random.randint(0, len(SUCCESSFUL_RESPONSES))] +
                               'Теперь укажите количество времени, которое необходимо для достижения цели. Вы можете '
                               'указать *число недель* (например, \"_7 недель_\"), *число месяцев* (например, \"'
                               '_3 месяца_\"), или просто ввести *конечную дату* (например, \"_10/12/2023_\")',
                               parse_mode='markdown', reply_markup=time_markup)
        bot.register_next_step_handler(msg, ask_goal_time)


date_pattern = r'^(\d{1,2})([\/\.])(\d{1,2})(\2)(\d{4}|\d{2})$'
months_weeks_pattern = r'^(\d+)\s([а-яА-Я]+)'


def ask_goal_time(message):
    if is_person_registered(message.chat.id) and message.text == '/exit':
        bot.send_message(message.chat.id, EXIT_RESPONDS[np.random.randint(0, len(EXIT_RESPONDS))])
        return

    if re.search(date_pattern, message.text):
        # dealing with date
        date_match = re.search(date_pattern, message.text)
        day = date_match.group(1)
        month = date_match.group(3)
        year = date_match.group(5)

        try:
            date = datetime(day=int(day), month=int(month), year=int(year))
            now = datetime.now()
            period_in_days = (date - now).days + 1  # number of days to finish the goal
        except ValueError:
            msg = bot.send_message(message.chat.id, 'Дата введена некорректно! Пожалуйста, введите другую дату.')
            bot.register_next_step_handler(msg, ask_goal_time)
            return
    else:
        # dealing not with date
        if re.search(months_weeks_pattern, message.text.lower()):
            period_match = re.search(months_weeks_pattern, message.text.lower())
            morph = pymorphy2.MorphAnalyzer()  # for lemmatizing
            parse = morph.parse(period_match.group(2))[0]
            if parse.normal_form == 'неделя':
                # dealing with weeks
                weeks = int(period_match.group(1))
                period_in_days = weeks * 7
            elif parse.normal_form == 'месяц':
                # dealing with months
                months = int(period_match.group(1))
                today = datetime.today()
                period_in_days = (add_months(today, months) - today).days + 1
            else:
                msg = bot.send_message(message.chat.id, 'Промежуток времени указан неверно. Пожалуйста, введите '
                                                        'временной промежуток еще раз или воспользуйтесь другим '
                                                        'способом ввода.')
                bot.register_next_step_handler(msg, ask_goal_time)
                return
        else:
            msg = bot.send_message(message.chat.id, 'Время введено некорректно. Пожалуйста, введите временной '
                                                    'промежуток для цели еще раз, воспользовавшись _одним из трёх_ '
                                                    'предложенных форматов ввода.', parse_mode='markdown')
            bot.register_next_step_handler(msg, ask_goal_time)
            return

    current_goal['period_in_days'] = period_in_days

    # adding the current goal to the goals list in the following format: {'goal_name': [amount, time_in_days]}

    deadline = datetime.today() + timedelta(days=period_in_days)

    # uploading current goal in database
    add_goal_to_db(message.chat.id, current_goal, deadline.strftime("%Y-%m-%d"))

    bot.send_message(message.chat.id, 'Цель \"*{}*\" добавлена в список ваших целей. Планируемая дата окончания цели: '
                                      '*{}*'.format(current_goal['name'], deadline.strftime("%d/%m/%Y")),
                     parse_mode='markdown')


@bot.message_handler(content_types=['text'], commands=['goals'])
def print_goals(message):
    if is_person_registered(message.chat.id):
        goals = get_goals_from_db(message.chat.id)
        goals_str = 'Вот список ваших финансовых целей:'

        if goals:
            # there are some goals associated with the user
            for i, goal in enumerate(goals):
                goal_name, amount, period_in_days, deadline = goal
                goals_str += f"\n{i + 1}. *{goal_name}*, сумма: *{amount}* {get_correct_form(amount, word='рубль')}, " \
                             f"длительность цели: *{period_in_days}* {get_correct_form(period_in_days)}, планируемая " \
                             f"дата достижения цели: *{deadline.strftime('%d/%m/%y')}*."
            # printing goals list
            bot.send_message(message.chat.id, goals_str, parse_mode='markdown')
        else:
            # there are no goals associated with the user
            bot.send_message(message.chat.id, 'У вас пока что нет никаких финансовых целей. Для добавления финансовой '
                                              'цели используйте /addgoal')
    else:
        bot.register_next_step_handler(message, start_message)


@bot.message_handler(content_types=['text'], commands=['delgoal'])
def delete_goal(message):
    if is_person_registered(message.chat.id):
        print_goals(message)
        if len(get_goals_from_db(message.chat.id)):
            msg = bot.send_message(message.chat.id, 'Введите номер цели, которую вы хотите удалить.')
            bot.register_next_step_handler(msg, del_goal_by_id)
    else:
        bot.register_next_step_handler(message, start_message)


def del_goal_by_id(message):
    # if a user typed in the command by mistake
    if is_person_registered(message.chat.id) and message.text == '/exit':
        bot.send_message(message.chat.id, EXIT_RESPONDS[np.random.randint(0, len(EXIT_RESPONDS))])
        return

    id_str = message.text
    if id_str.isdigit():
        # the id is a digit
        goal_id = int(id_str)
        goals = get_goals_from_db(message.chat.id)
        if goal_id <= len(goals):
            # deleting the goal
            global database, user, password, host, port
            con = psycopg2.connect(
                database=database,
                user=user,
                password=password,
                host=host,
                port=port
            )
            cur = con.cursor()
            cur.execute(f'''DELETE FROM goals WHERE goals.chat_id = {message.chat.id} AND goals.name = 
                        {goals[goal_id - 1][0]}' ''')
            con.commit()
            con.close()

            bot.send_message(message.chat.id, f'Цель "*{goals[goal_id - 1][0]}*" успешно удалена из вашего списка '
                                              f'целей.',
                             parse_mode='markdown')
        else:
            msg = bot.send_message(message.chat.id, 'Номер цели превышает количество целей. Пожалуйста, введите другой '
                                                    'номер.')
            bot.register_next_step_handler(msg, del_goal_by_id)

    else:
        # the id entered is not a number
        msg = bot.send_message(message.chat.id, 'Номер цели введен некорректно, пожалуйста, введите номер еще раз.')
        bot.register_next_step_handler(msg, del_goal_by_id)


@bot.message_handler(content_types=['text'], commands=['setregexp'])
def set_regular_expenses(message):
    if is_person_registered(message.chat.id):
        msg = bot.send_message(message.chat.id, 'Пожалуйста, укажите ваши среднемесячные регулярные траты. К'
                                                ' регулярным тратам можно отнести траты, которые выплачиваются '
                                                'ежемесячно, размер которых остается постоянным от месяца к месяцу. '
                                                'Примеры регулярных трат:\n'
                                                '- *Выплаты по кредитам (при постоянных выплатах)*\n'
                                                '- *Оплата дополнительного образования детей (музыкальная школа, школа '
                                                'искусств, спортивная секция)*\n'
                                                '- *Личные траты (маникюр, салон красоты)*\n'
                                                'Введите _сумму денег_, которая характеризует ваши постоянные траты.',
                               parse_mode='markdown')
        bot.register_next_step_handler(msg, ask_regular_expenses_money)
    else:
        bot.register_next_step_handler(message, start_message)


def ask_regular_expenses_money(message):
    # if a user typed in the command by mistake
    if is_person_registered(message.chat.id) and message.text == '/exit':
        bot.send_message(message.chat.id, EXIT_RESPONDS[np.random.randint(0, len(EXIT_RESPONDS))])
        return

    regular_expenses_str = message.text
    if not regular_expenses_str.isdigit():
        msg = bot.send_message(message.chat.id, 'Число введено некорректно. Пожалуйста, введите сумму ваших регулярных '
                                                'трат еще раз еще раз.')
        bot.register_next_step_handler(msg, ask_regular_expenses_money)
    else:
        regular_expenses = int(regular_expenses_str)
        update_db(message.chat.id, 'bot_user', {'regexp': regular_expenses})
        bot.send_message(message.chat.id, SUCCESSFUL_RESPONSES[np.random.randint(0, len(SUCCESSFUL_RESPONSES))] +
                         f"Сумма регулярных трат равна *{regular_expenses}* "
                         f"{get_correct_form(regular_expenses, word='рубль')}.",
                         parse_mode='markdown')


# Add expense by NLP processing
@bot.message_handler(content_types=['text'], commands=['add'])
def add_expense(message):
    if is_person_registered(message.chat.id):
        msg = bot.send_message(message.chat.id, f'Пожалуйста, напишите название вашей траты, а я попробую ее '
                                                f'классифицировать. Например, '
                                                f'"_{EXPANSES_EXAMPLES[np.random.randint(0, len(EXPANSES_EXAMPLES))]}'
                                                f'_".', parse_mode='markdown')
        bot.register_next_step_handler(msg, ask_expense)
    else:
        bot.register_next_step_handler(message, start_message)


def ask_expense(message):
    # if a user typed in the command by mistake
    if is_person_registered(message.chat.id) and message.text == '/exit':
        bot.send_message(message.chat.id, EXIT_RESPONDS[np.random.randint(0, len(EXIT_RESPONDS))])
        return

    if len(re.findall(r'\d+', message.text)) != 1:
        # given message contains more than one digit
        msg = bot.send_message(message.chat.id, 'Предложение должно включать одно число (без знаков разделения), '
                                                'характеризующее трату. Пожалуйста, введите название вашей траты '
                                                'еще раз.')
        bot.register_next_step_handler(msg, ask_expense)

    else:
        # clean sentence
        txt_clean = clean_sentences([message.text], additional_stopwords=['рубль', 'р', 'руб'])
        predicted_prob = model.predict_proba(txt_clean)[0]
        threshold = 0.55

        global exp_name, amount, predicted_category
        # predicting a category
        predicted_category = (MODEL_CATEGORIES[np.where(predicted_prob == max(predicted_prob))[0][0]]
                              if max(predicted_prob) > threshold else 'ДРУГОЕ')

        exp_name, amount = parse_expense(message.text)

        # adding expanse to db
        # todo вставить добавление траты в базу данных сюда (функцию check_category удалить)

        if exp_name:
            # expenditure name is not empty
            bot.send_message(message.chat.id, f'{SUCCESSFUL_RESPONSES[np.random.randint(0, len(SUCCESSFUL_RESPONSES))]}'
                                              f'Трата "*{exp_name}*" добавлена в категорию "*{predicted_category}*". '
                                              f'Сумма траты: *{amount}* {get_correct_form(amount, word="рубль")}.',
                             parse_mode='markdown')
        else:
            # expenditure name is empty
            msg = bot.send_message(message.chat.id, 'Название траты не может быть пустым. Пожалуйста, укажите название '
                                                    'траты.')
            bot.register_next_step_handler(msg, ask_expense)
            return

        # test section to check classifier's work
        yes_no_markup = types.ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True)
        yes_no_markup.add('Да')
        yes_no_markup.add('Нет')

        msg = bot.send_message(message.chat.id, 'Правильно ли определена категория?', reply_markup=yes_no_markup)

        bot.register_next_step_handler(msg, check_category)


exp_name = ''
amount = 0  # todo delete after all 3 vars
predicted_category = ''


# todo check and delete after (function for checking classifier)
def check_category(message):
    if message.text == 'Да':
        # category classified correctly
        add_expense_to_db(message.chat.id, exp_name, amount,
                          predicted_category, is_correct=True)  # todo move to ask_expanse
        bot.send_message(message.chat.id, f'{SUCCESSFUL_RESPONSES[np.random.randint(0, len(SUCCESSFUL_RESPONSES))]}'
                                          f'Спасибо!')
    elif message.text == 'Нет':
        # category classified incorrectly
        add_expense_to_db(message.chat.id, exp_name, amount,
                          predicted_category, is_correct=False)
        bot.send_message(message.chat.id, f'{SUCCESSFUL_RESPONSES[np.random.randint(0, len(SUCCESSFUL_RESPONSES))]}'
                                          f'Исправлюсь!')
    else:
        msg = bot.send_message(message.chat.id,
                               f'{WRONG_COMMAND_RESPONSES[np.random.randint(0, len(WRONG_COMMAND_RESPONSES))]}'
                               f'Пожалуйста, напишите *Да* или *Нет*', parse_mode='markdown')
        bot.register_next_step_handler(msg, check_category) # check a


@bot.message_handler(content_types=['text'], commands=['delete'])
def delete_last_expense(message):
    if is_person_registered(message.chat.id):
        global database, user, password, host, port
        con = psycopg2.connect(
            database=database,
            user=user,
            password=password,
            host=host,
            port=port
        )
        cur = con.cursor()

        cur.execute(f'''SELECT e.name FROM expenditures as e WHERE e.chat_id = {message.chat.id} 
                        AND e.datetime = (SELECT e.datetime FROM expenditures as e WHERE e.chat_id = {message.chat.id} 
                        ORDER BY e.datetime DESC LIMIT 1)''')

        select_res = cur.fetchall()

        cur.execute(f'''DELETE FROM expenditures as e WHERE e.chat_id = {message.chat.id} 
                    AND e.datetime = (SELECT e.datetime FROM expenditures as e WHERE e.chat_id = {message.chat.id} 
                    ORDER BY e.datetime DESC LIMIT 1)''')

        con.commit()
        con.close()

        if select_res:
            bot.send_message(message.chat.id, f'Трата "*{select_res[0][0]}*" успешно удалена!', parse_mode='markdown')
        else:
            bot.send_message(message.chat.id, 'Список ваших трат пуст!')
    else:
        bot.register_next_step_handler(message, start_message)


@bot.message_handler(content_types=['text'], commands=['details'])
def details(message):
    if is_person_registered(message.chat.id):
        global database, user, password, host, port

        # connecting to db
        con = psycopg2.connect(
            database=database,
            user=user,
            password=password,
            host=host,
            port=port
        )
        cur = con.cursor()
        cur.execute(f'''SELECT DISTINCT e.category FROM expenditures as e WHERE e.chat_id = {message.chat.id} 
                    ORDER BY e.category ASC''')
        select_res = cur.fetchall()

        # if there are records in the db
        if select_res:
            categories_in_db = [sel[0] for sel in select_res]

            # collecting sum of expenditures by each category
            chart_values = []
            today_date = datetime.today()
            date_month_ago = add_months(datetime.today(), -1)
            for category in categories_in_db:
                cur.execute(f'''SELECT SUM(e.amount) FROM expenditures as e WHERE 
                            e.category = '{category}' AND e.datetime > '{date_month_ago.strftime("%Y-%m-%d %H:%M:%S")}' 
                            AND e.chat_id = {message.chat.id}''')
                chart_values.append(cur.fetchall()[0][0])

            def save_fig():
                # plotting pie chart
                fig, ax = plt.subplots(figsize=(6, 3), subplot_kw=dict(aspect="equal"))

                def func(pct, allvals):
                    absolute = pct / 100. * np.sum(allvals)
                    return "{:.1f}%\n({:.0f} руб.)".format(pct, absolute)

                wedges, texts, autotexts = ax.pie(chart_values, autopct=lambda pct: func(pct, chart_values),
                                                  textprops=dict(color="w"))
                ax.legend(wedges, categories_in_db,
                          title="Категории трат",
                          loc="center left",
                          bbox_to_anchor=(1, 0, 0.5, 1))
                plt.setp(autotexts, size=8, weight="bold")
                ax.set_title(r'Финансовый отчет с $\bf{' + f'{date_month_ago.strftime("%d/%m/%y")}' +
                             '}$ по ' + r'$\bf{' + f'{today_date.strftime("%d/%m/%y")}' + '}$')
                plt.savefig('diagram.png')

            # sending figure
            save_fig()
            bot.send_message(message.chat.id, 'Вот ваш финансовый отчет за текущий месяц.')
            bot.send_photo(message.chat.id, open('diagram.png', 'rb'))
        else:
            bot.send_message(message.chat.id, 'Список ваших трат пуст. Для добавления траты используйте /add.')

        con.commit()
        con.close()
    else:
        bot.register_next_step_handler(message, start_message)


@bot.message_handler(content_types=['text'], commands=['advice'])
def advice(message):
    if is_person_registered(message.chat.id):
        reg_exp = get_reg_exp(message.chat.id)  # regular expenditures
        if reg_exp:
            # user has set up the amount already
            income = get_income(message.chat.id)
            daily_available = (income - reg_exp) * 12 / 365

            # calculating how good a user following his financial goals
            week_exp_by_day = np.array(get_week_exp(message.chat.id))

            # collecting the week statistics
            percent = round(((week_exp_by_day / np.array([daily_available] * 7) - 1) * 100).mean())

            if percent < 0:
                bot.send_message(message.chat.id, f'{COMPLIMENT_RESPONDS[np.random.randint(0, len(COMPLIMENT_RESPONDS))]}'
                                                  f'За прошедшую неделею в среднем вы тратили на *{abs(percent)}%* '
                                                  f'меньше, чем было запланированно! Так держать!',
                                 parse_mode='markdown')
            elif percent > 0:
                bot.send_message(message.chat.id, f'{CHEER_UP_RESPONDS[np.random.randint(0, len(CHEER_UP_RESPONDS))]}'
                                                  f'В среднем за прошедрую неделю вы тратили на *{abs(percent)}%* '
                                                  f'больше, чем было запланированно. Постарайтей тратить чуть меньше '
                                                  f'на этой неделе, чтобы достичь всех ваших финансовых целей в '
                                                  f'запланированное время.', parse_mode='markdown')
            else:
                bot.send_message(message.chat.id, f'{COMPLIMENT_RESPONDS[np.random.randint(0, len(COMPLIMENT_RESPONDS))]}'
                                                  f'Идете строго по графику!')
        else:
            # user hasn't set up the amount
            bot.send_message(message.chat.id, 'Для корректной работы функции /advice, пожалуйста, укажите ваши '
                                              'регулярные траты с помощью /setregexp')
    else:
        bot.register_next_step_handler(message, start_message)

# A default answer (in case a user fails to enter a command from the list of commands)


@bot.message_handler(content_types=['text'])
def default_answer(message):
    if is_person_registered(message.chat.id):
        respond = (WRONG_COMMAND_RESPONSES[np.random.randint(0, len(WRONG_COMMAND_RESPONSES))] +
                   'Используй /help.')
        bot.send_message(message.chat.id, respond)
    else:
        bot.register_next_step_handler(message, start_message)


@bot.message_handler
def error_message(message):
    bot.send_message(message.chat.id, 'Возникла проблема с загрузкой базы данных... Пожалуйста, обратитесь к '
                                      'администратору.')


""" Additional functions used by handlers up there """


def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return datetime(day=day, month=month, year=year)


def create_db():
    global database, user, password, host, port
    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()

    # todo delete column correct
    cur.execute('''
                CREATE TABLE IF NOT EXISTS bot_user (
                    chat_id INT PRIMARY KEY,
                    name TEXT NOT NULL,
                    income INT NOT NULL,
                    regexp INT
                );
                
                CREATE TABLE IF NOT EXISTS goals (
                    chat_id INT NOT NULL,
                    name TEXT NOT NULL,
                    money INT NOT NULL,
                    time_in_days INT NOT NULL,
                    deadline DATE NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES bot_user (chat_id)
                );
                
                CREATE TABLE IF NOT EXISTS expenditures (
                    chat_id INT NOT NULL,
                    name TEXT NOT NULL,
                    amount INT NOT NULL,
                    category TEXT NOT NULL,
                    datetime TIMESTAMP NOT NULL,
                    correct INT NOT NULL,
                    FOREIGN KEY (chat_id) REFERENCES bot_user (chat_id)
                )
                
                ''')
    con.commit()
    con.close()


def add_user_to_db(chat_id, name, income):
    global database, user, password, host, port
    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()

    cur.execute(f'''INSERT INTO bot_user VALUES ({chat_id}, '{name}', {income})''')
    con.commit()
    con.close()


def is_person_registered(chat_id):
    global database, user, password, host, port
    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()
    cur.execute(f'''SELECT chat_id FROM bot_user WHERE bot_user.chat_id = {chat_id}''')

    # cur.fetchall () returns a list of tuple if a row in a database is found (thus, True value). Otherwise it returns
    # an empty list which is interpreted as a False value
    return True if cur.fetchall() else False


def update_db(chat_id, table, vals_dict):
    global database, user, password, host, port
    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()
    for attr in vals_dict:
        cur.execute(f'''UPDATE {table} SET {attr} = '{vals_dict[attr]}' WHERE chat_id = {chat_id}''')

    con.commit()
    con.close()


def add_goal_to_db(chat_id, goal, deadline):
    global database, user, password, host, port

    goal_name = goal['name']
    amount = goal['amount']
    period_in_days = goal['period_in_days']

    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()
    cur.execute(f'''INSERT INTO goals VALUES ({chat_id}, '{goal_name}', {amount}, {period_in_days}, '{deadline}')''')

    con.commit()
    con.close()


def get_goals_from_db(chat_id):
    global database, user, password, host, port
    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()
    cur.execute(f'''SELECT
                        goals.name,
                        goals.money,
                        goals.time_in_days,
                        goals.deadline
                    FROM goals
                    WHERE goals.chat_id = {chat_id}''')

    # Returning goals list
    return cur.fetchall()


def add_expense_to_db(chat_id, exp_name, amount, category, is_correct):  # todo delete last parameter
    global database, user, password, host, port

    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()
    cur.execute(f'''INSERT INTO expenditures VALUES ({chat_id}, '{exp_name}', {amount}, '{category}', 
                TIMESTAMP '{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', {1 if is_correct else 0} )''')  # todo delete last column

    con.commit()
    con.close()


def get_reg_exp(chat_id):
    global database, user, password, host, port

    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()
    cur.execute(f'''SELECT bu.regexp FROM bot_user as bu WHERE bu.chat_id = {chat_id}''')

    reg_exp = cur.fetchall()[0][0]

    con.commit()
    con.close()

    return reg_exp


def get_income(chat_id):
    global database, user, password, host, port

    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()
    cur.execute(f'''SELECT bu.income FROM bot_user as bu WHERE bu.chat_id = {chat_id}''')

    reg_exp = cur.fetchall()[0][0]

    con.commit()
    con.close()

    return reg_exp


# This function returns week expenditures
def get_week_exp(chat_id):
    global database, user, password, host, port

    con = psycopg2.connect(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cur = con.cursor()

    week_exp = []
    dates = [datetime.today() + timedelta(days=i) for i in range(-7, 0)]
    for date in dates:
        cur.execute(f'''SELECT SUM(e.amount) FROM expenditures as e WHERE e.chat_id = {chat_id} AND e.datetime > 
                    '{date.strftime("%Y-%m-%d")}' AND e.datetime < 
                    '{(date + timedelta(days=1)).strftime("%Y-%m-%d")}' ''')
        res = cur.fetchall()[0][0]
        week_exp.append(res if res else 0)

    con.commit()
    con.close()

    return week_exp


def get_correct_form(number, word='день'):
    forms = {
        'день': ['дней', 'день', 'дня'],
        'неделя': ['недель', 'неделя', 'недели'],
        'рубль': ['рублей', 'рубль', 'рубля']
    }

    number = int(str(number)[-2:])  # getting last 2 digits
    if 11 <= number <= 20:
        return forms[word][0]
    else:
        number = int(str(number)[-1])  # getting last digit
        if number == 1:
            return forms[word][1]
        elif 2 <= number <= 4:
            return forms[word][2]
        else:
            return forms[word][0]


# The function looks for expense name and amount of money spent on the expense
def parse_expense(expense_str):
    original_str = expense_str
    stop_words = nltk.corpus.stopwords.words('russian') + ['рубль', 'р', 'руб']
    morph = pymorphy2.MorphAnalyzer()
    expense_str_words = re.findall(r'[а-яa-z\d]+', expense_str.lower())
    normal_words = [morph.parse(word)[0].normal_form for word in expense_str_words]
    words = [word for word in normal_words if word not in stop_words]

    if len(words) > 1:
        # looking for the amount
        amount = 0
        for i, word in enumerate(words):
            if word.isdigit():
                amount = int(word)
                del words[i]

                # checking surrounding (russian language feature)
                if 'трат' in words[i - 1]:
                    del words[i - 1]
                if i + 1 < len(words):
                    if 'трат' in words[i + 1]:
                        del words[i + 1]
    else:
        return None, None

    beginning_is_found = False
    start_ind = 0
    end_ind = -1
    for word in words:
        # looking where we have word in expense_str
        for exp_str_word in expense_str_words:
            if morph.parse(exp_str_word)[0].normal_form == word:
                # the word is found
                if not beginning_is_found:
                    start_ind = re.search(exp_str_word, expense_str.lower()).start()
                    beginning_is_found = True
                # deleting all words before the word found
                end_ind += re.search(exp_str_word, expense_str.lower()).end()
                expense_str_words.remove(exp_str_word)
                expense_str = original_str[end_ind + 1:]
                break

    result_str = original_str[start_ind:end_ind + 1]
    return result_str[0].replace(result_str[0], result_str[0].capitalize()) + result_str[1:], amount


model = pickle.load(open('model.pkl', 'rb'))

create_db()

while True:
    try:
        bot.polling()
    except requests.exceptions.ConnectTimeout:
        print('LOG: Connection refused. Reconnecting...')
        time.sleep(SECS_BEFORE_RECONNECT)
