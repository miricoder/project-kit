# Acceptance criteria for Dumpit v1 (proposal Phases 0–2).
# Contract for /test. Scenario names that appear in docs/spec.md "Failure modes" must match exactly.
# Unless a scenario says otherwise: today is Monday 23 February 2026, 09:00, time zone
# Europe/Lisbon, home currency EUR, the phone is online, and the store is empty.

Feature: Filing test set (Phase 0)

  Scenario: filing test set reports a fully-correct score
    Given the filing test set holds 200 captures covering tasks, expenses, trips, edits and 3 pasted notes
    When the scorer is run against the filing service
    Then it prints the share of captures filed fully correctly for each item kind and overall
    And it prints the mean cost per capture in euros
    And it writes eval/report.json with one result per capture id

  Scenario: tasks and expenses reach the Phase 1 accuracy bar
    Given the task and expense captures in the filing test set
    When the scorer is run against the filing service
    Then at least 90% of those captures are filed fully correctly

  Scenario: the whole test set reaches the v1 accuracy bar
    Given all 200 captures in the filing test set
    When the scorer is run against the filing service
    Then at least 90% of them are filed fully correctly


Feature: Capture and filing

  Scenario: a typed expense is filed against the month
    Given a monthly budget of €1,400
    When the user sends "paid 42 for groceries"
    Then an expense of €42.00 dated 23 February 2026 in category "Groceries" exists
    And the capture log shows the line "Expense €42 · Groceries · today" with an Undo button
    And the February budget shows €42 spent and €1,358 left

  Scenario: a task with a day and time is filed with a reminder
    When the user sends "dentist Thursday 3pm"
    Then a task "Dentist" due Thursday 26 February 2026 at 15:00 exists
    And a reminder notification is scheduled for 26 February 2026 at 15:00

  Scenario: a reminder fires with the phone locked
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00
    And the phone is locked and the app is not running
    When the clock reaches 26 February 2026 at 15:00
    Then a notification "Dentist" is shown within 60 seconds

  Scenario: one sentence becomes two items
    When the user sends "paid 42 for groceries and book the car service"
    Then exactly one expense of €42.00 in category "Groceries" exists
    And exactly one task "Book the car service" with no due date exists
    And the capture log shows two filed lines, each with its own Undo button

  Scenario: an expense without a date is filed as today
    When the user sends "coffee 3.50"
    Then an expense of €3.50 dated 23 February 2026 exists

  Scenario: the monthly budget is set by saying it
    When the user sends "my budget is 1400 a month"
    Then the Dashboard shows a February budget of €1,400 with €1,400 left

  Scenario: dictated text is filed like typed text
    Given the keyboard's dictation has put "paid 42 for groceries" in the capture box
    When the user taps Send
    Then an expense of €42.00 in category "Groceries" exists

  Scenario: capture that is not understood is kept as a note
    When the user sends "the thing with Marta"
    Then no task, expense or trip is created
    And the capture log shows "Saved as a note. Is it one of these?" with at most 3 suggestions

  Scenario: implausible amount is not filed as an expense
    When the user sends "paid 4200000 for coffee"
    Then no expense is created
    And the capture is kept as a note

  Scenario: capture over 4,000 characters is not sent
    Given the capture box holds 4,001 characters
    When the user taps Send
    Then nothing is sent to the filing service
    And the text is still in the capture box
    And the message "Too long to file in one go: 4,001 of 4,000 characters" is shown

  Scenario: captures are filed in the order they were said
    Given the phone is offline
    And the user has sent "paid 42 for groceries" and then "that was 24 not 42"
    When the connection returns
    Then exactly one Groceries expense exists and its amount is €24.00


Feature: Edit by saying so

  Scenario: a task is moved by saying so
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00
    When the user sends "move the dentist to Friday"
    Then the task "Dentist" is due Friday 27 February 2026 at 15:00
    And the reminder for 26 February is cancelled and one for 27 February at 15:00 is scheduled
    And the capture log shows "Moved · Dentist → Fri 27 Feb, 15:00" with an Undo button

  Scenario: an amount is corrected by saying so
    Given an expense of €42.00 "groceries" dated 23 February 2026
    When the user sends "that was 24 not 42"
    Then that expense's amount is €24.00
    And no new expense is created

  Scenario: a task is cancelled by saying so
    Given a task "Book the car service" with no due date
    When the user sends "cancel the car service"
    Then the task "Book the car service" no longer appears on the Dashboard

  Scenario: correction applies to the most recent matching expense
    Given an expense of €42.00 "groceries" dated 20 February 2026
    And an expense of €42.00 "groceries" dated 23 February 2026
    When the user sends "that was 24 not 42"
    Then the expense dated 23 February 2026 is €24.00
    And the expense dated 20 February 2026 is still €42.00

  Scenario: correction that matches nothing changes nothing
    Given an expense of €42.00 "groceries" dated 23 February 2026
    When the user sends "that was 15 not 80"
    Then no expense, task or trip is changed
    And the capture is kept as a note

  Scenario: twenty test corrections meet the Phase 1 bar
    Given 20 correction captures from the filing test set, each with its starting items
    When each correction is sent
    Then at least 18 change exactly the intended item and nothing else

  Scenario: one capture cannot change more than five existing items
    Given 6 open tasks whose titles contain "call"
    When the user sends "cancel all the calls"
    Then all 6 tasks are still open
    And the capture is kept as a note


Feature: Undo and redo

  Scenario: undo restores the previous state in one tap
    Given the user sent "paid 42 for groceries" and an expense of €42.00 was filed
    When the user taps "Undo expense €42 groceries"
    Then no Groceries expense exists
    And the February spent figure goes back to its value before the capture
    And the button now reads "Redo"

  Scenario: redo re-applies an undone item
    Given the user undid the expense of €42.00 groceries
    When the user taps "Redo"
    Then an expense of €42.00 in category "Groceries" exists again

  Scenario: undo of a move restores the old due date
    Given the user sent "move the dentist to Friday" and the task moved from 26 to 27 February
    When the user taps Undo on that line
    Then the task "Dentist" is due Thursday 26 February 2026 at 15:00
    And a reminder is scheduled for 26 February 2026 at 15:00

  Scenario: undo of an item changed since is refused
    Given the user sent "paid 42 for groceries"
    And then sent "that was 24 not 42"
    When the user taps Undo on the first capture's line
    Then the expense is still €24.00
    And the message "Changed since — say the correction instead" is shown

  Scenario: undo all reverts every item from a paste
    Given a pasted note produced 6 items
    When the user taps "Undo all"
    Then none of the 6 items exists


Feature: Pasted notes

  Scenario: a pasted note becomes several items
    Given the clipboard holds the text:
      """
      groceries 38.20
      dentist thu 3pm
      lisbon hotel deposit 120
      renew gym
      """
    And a trip "Lisbon" from 13 to 16 March 2026 exists
    When the user taps Paste and then Send
    Then 4 items are filed: an expense of €38.20, a task "Dentist" due 26 February at 15:00, an expense of €120.00 linked to "Lisbon", and a task "Renew gym"
    And the Pasted notes screen shows "Filed 4 items" with an "Undo all" button

  Scenario: pasted notes cannot change or delete existing items
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00
    And the clipboard holds "cancel the dentist. groceries 12"
    When the user taps Paste and then Send
    Then the task "Dentist" is still due 26 February 2026 at 15:00
    And no expense is created
    And the capture is kept as a note

  Scenario: the paste button is disabled with an empty clipboard
    Given the clipboard is empty
    When the Dashboard is shown
    Then the Paste button is disabled


Feature: Offline and service failures

  Scenario: capture sent while offline is filed after reconnecting
    Given the phone is in airplane mode and the app is open
    When the user sends "paid 42 for groceries"
    Then the capture log shows "Waiting to file · you were offline"
    And when airplane mode is turned off an expense of €42.00 exists within 30 seconds
    And the waiting row is replaced by "Expense €42 · Groceries · today"

  Scenario: relative date in a queued capture resolves to the day it was said
    Given the phone was offline on Monday 23 February 2026 at 22:00
    And the user sent "dentist tomorrow 3pm" then
    When the connection returns on Tuesday 24 February 2026 at 08:00
    Then the task "Dentist" is due Tuesday 24 February 2026 at 15:00

  Scenario: app closed mid-filing files the capture exactly once
    Given the user sent "paid 42 for groceries"
    And the app was closed after the filing service replied but before the result was saved
    When the app is opened again
    Then exactly one expense of €42.00 exists

  Scenario: filing service error keeps the words and offers retry
    Given the filing service returns an error for every request
    When the user sends "paid 42 for groceries"
    Then after 2 automatic retries the capture shows "Couldn't file this. Your words are saved; nothing was lost."
    And a Retry button is shown
    And when the service recovers and the user taps Retry an expense of €42.00 exists

  Scenario: invalid model output is never applied
    Given the model returns output that breaks the op schema twice for the same capture
    When the user sends "paid 42 for groceries"
    Then no item is created or changed
    And the capture shows "Couldn't file this. Your words are saved; nothing was lost." with Retry

  Scenario: daily filing limit reached keeps captures waiting
    Given this install has filed 200 captures today
    When the user sends "paid 42 for groceries"
    Then the capture shows "Waiting to file · daily limit reached, files tomorrow"
    And no expense is created today


Feature: Reminders

  Scenario: reminders without exact alarm permission warn the user
    Given the app does not have the exact alarm permission
    When the user sends "dentist Thursday 3pm"
    Then the task is filed and a reminder is scheduled
    And the Dashboard shows a banner "Reminders may be a few minutes late" with a button to the setting

  Scenario: reminder keeps its wall-clock time after a time zone change
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00 created in Europe/Lisbon
    When the phone's time zone changes to Europe/Berlin
    Then the reminder is scheduled for 26 February 2026 at 15:00 Europe/Berlin

  Scenario: ticking a task done cancels its reminder
    Given a task "Dentist" due Thursday 26 February 2026 at 15:00
    When the user ticks the task's checkbox
    Then no reminder for "Dentist" is scheduled


Feature: Monthly budget and dashboard

  Scenario: the dashboard shows due tasks, the month and the active trip
    Given a monthly budget of €1,400 and €912 of February expenses
    And a task "Check passport expiry" due today
    And a trip "Lisbon" from 13 to 16 March 2026 with a budget of €600 and €214 spent
    When the Dashboard is opened
    Then "Due soon" lists "Check passport expiry" marked "Today"
    And the month card shows "€488 left" and "€912 spent"
    And the trip card shows "€386 left" of €600

  Scenario: month totals by category show the top three
    Given February expenses of €300 Groceries, €200 Eating out, €150 Transport and €50 Fun
    When the Dashboard is opened
    Then the month card lists Groceries €300, Eating out €200 and Transport €150 and not Fun

  Scenario: month over budget says how much over
    Given a monthly budget of €1,400 and €1,450 of February expenses
    When the Dashboard is opened
    Then the month card shows "€50 over" instead of an amount left
    And the progress bar is full

  Scenario: a dashboard with nothing due says so
    Given no task is due in the next 7 days
    When the Dashboard is opened
    Then the "Due soon" card shows "Nothing due this week."


Feature: Trips

  Scenario: a trip is created from one sentence with backward-scheduled to-dos
    When the user sends "Lisbon long weekend 13–16 March, about 600 all in"
    Then a trip "Lisbon" from 13 March 2026 to 16 March 2026 with a budget of €600 exists
    And the trip has 5 to-dos, each due before 13 March 2026:
      | to-do                   | due              | why                                   |
      | Book travel             | 23 February 2026 | 42 days before is past, so due today  |
      | Book stay               | 23 February 2026 | 35 days before is past, so due today  |
      | Check passport/ID       | 23 February 2026 | 28 days before is past, so due today  |
      | Pay remaining balances  | 6 March 2026     | 7 days before departure               |
      | Pack                    | 12 March 2026    | 1 day before departure                |

  Scenario: to-dos for a trip departing soon are due no later than departure
    When the user sends "Porto this Friday to Sunday, 250 budget"
    Then a trip "Porto" from 27 February 2026 to 1 March 2026 exists
    And every to-do of that trip is due between 23 February 2026 and 26 February 2026

  Scenario: an expense that names the trip is linked to it
    Given a trip "Lisbon" from 13 to 16 March 2026
    When the user sends "lisbon hotel deposit 120"
    Then an expense of €120.00 dated 23 February 2026 is linked to the trip "Lisbon"
    And it also counts in February's spending

  Scenario: an expense during the trip dates is linked by date
    Given a trip "Lisbon" from 13 to 16 March 2026
    And today is 14 March 2026
    When the user sends "coffee 3.50"
    Then the expense of €3.50 is linked to the trip "Lisbon"

  Scenario: expense inside two overlapping trips links to the later one
    Given a trip "Lisbon" from 13 to 16 March 2026
    And a trip "Sintra" from 15 to 15 March 2026
    And today is 15 March 2026
    When the user sends "lunch 18"
    Then the expense of €18.00 is linked to the trip "Sintra"
    And the capture log line names "Sintra" with an Undo button

  Scenario: trip spent equals the sum of its linked expenses
    Given a trip "Lisbon" with linked expenses of €120.00, €3.50 and €90.50
    When the Trip screen for "Lisbon" is opened
    Then it shows €214 spent and €386 left of €600

  Scenario: trip without a budget shows no budget set
    When the user sends "Madrid 2 to 5 April"
    Then the trip card for "Madrid" shows "No budget set"

  Scenario: fewer than one in ten captures need a fix during 14 days of use
    Given one person has used Dumpit as their only life-admin capture tool for 14 days
    When their captures and undo or correction actions are counted
    Then fewer than 1 in 10 captures were followed by an undo or a correction


Feature: Data safety on upgrade and rollback

  Scenario: failed database upgrade leaves data unchanged
    Given a store at schema 1 with 50 expenses and 10 tasks
    And a migration to schema 2 that fails partway
    When the app is updated and opened
    Then the store is still at schema 1 with 50 expenses and 10 tasks
    And a copy named "dumpit.v1.bak" exists
    And the app shows "Couldn't finish updating your data. Nothing was lost."

  Scenario: rolled-back app version opens data written by the newer version
    Given app build N wrote a store at schema 2 with min_reader_version 1 holding 50 expenses
    When build N−1, rebuilt with a higher version code, is installed over it
    Then the Dashboard opens without error
    And all 50 expenses are listed with their amounts unchanged
