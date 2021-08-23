# Keeper Bot

***Keeper Bot*** is a telegram bot that collects the information about personal incomes and spendings and visualizes the dynamics by different kinds of expenditures. Also the bot is able to help people to reach financial goals by simple linear planning expenditures mechanism.

## Main Features
1. Convenient way to analyze how much you spend on different kinds of spendings
2. Embedded machine learning model to process native language
3. Nice Matplotlib diagrams sent directly to a user by telegram

## Description

The idea of this project is to let Russian-speaking people an opportunity to keep counting up their spendings and set up new financial goals using telegram bot. The application supports Native Language Processing for Russian which makes the process of adding new spendings a bit like a "talk with a real person".

## User-Service Interaction Scenario

A typical user-service interaction scenario looks like this.

1. A user sends */start* message to the bot
    * A bot asks user to specify his name and checks it
    * A bot asks user to provide info on his average monthly income
2. The bot sends user a list of commands
3. Bot is waiting for a command from the registered user
4. Every week the bot will visualize the user's spendings statistics by kinds of expenditures

## Commands List

- */help* - print a list of commands
- */changename* - change a user name
- */setincome* - rewrite an average monthly income
- */addgoal* - setup a new financial goal:
    * The bot asks for a goal name
    * The bot asks for amount of money to reach the goal
    * The bot asks for a desired period of time to reach the goal
- */goals* - print list of current financial goals
- */delgoal* - remove financial goal
- */add* - add a spending (ML model is used to process native language)
- */delete* - remove a user's last spending
- */details* - show expenditures diagram for a current month by six kinds of spendings:
    * Public utilities
    * Food
    * Transportation
    * Health
    * Entertainment
    * Other
- */advice* - the bot comments how well you follow your financial goals (do your spendings fit in your goals or your should spend less)

## How NLP Is Processed

As it was mentioned above, the bot uses Multiclass *Naive Bayes Classifier model* to process native Russian language and classify to what kind of expenditures a user's message should belong.

The workflow can be described in the following way:
1. A user enters a message characterizing his last spending in Russian, for example:
``` "Вчера заправил машину на АЗС на 2500 рублей" ```
2. Entered text is cleaned, non-target words get removed
3. The cleaned text is vectorized using Bag Of Words strategy
4. ML model predicts the probability of each of five expenditures categories (Public utilities, Food, Transportation, Health and Entertainment). If maximum probability is less than a specific threshold value, the expenditure from user's message is classified as `"Other"`.
