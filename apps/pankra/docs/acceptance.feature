Feature: Training plan as whiteboard cards

  Scenario: a session shows as a fully spelled-out card
    Given a gym session on 2026-11-25 with 4 rounds of 50 m sled push at 202 kg
    And the profile sled mat is 12.5 m
    When the athlete opens Today on 2026-11-25
    Then the card shows "50 m · 4 lengths · 202 kg"
    And the card shows where the 1:30 rest goes
    And the card shows no daily push and core block

  Scenario: adding a class moves later sessions
    Given sessions planned Tue 24, Wed 25, Thu 26, Fri 27 and Sun 29 Nov, with Sat 28 as rest
    When the athlete adds a box class on Tue 24 Nov
    Then Tue 24 shows the class
    And the Tue session shows on Wed 25 with status "Moved"
    And the Fri session shows on Sun 29
    And Sat 28 is still a rest day

  Scenario: a pushed session crosses into next week
    Given the Sun 29 Nov session is the last planned session of the week
    When a class is added on Tue 24 Nov
    Then the Sun 29 Nov session moves to Mon 30 Nov
    And the change list says it moved into next week

Feature: Results and feedback

  Scenario: a result gets feedback against the plan
    Given a prescription of 5 x 1 km at 13.0 km/h on the Air runner
    And a logged result of 0.94, 0.89, 0.90, 0.90 and 0.86 km in 4:10 each
    When the athlete runs result-analyzer
    Then the feedback names a fade from 0.94 km to 0.86 km
    And it gives between 2 and 3 tips

  Scenario: screenshot values need confirmation
    Given a Hyrox results screenshot showing Running 1 as 00:02:59
    When the athlete uploads it
    Then the extracted values are shown with Running 1 = 2:59
    And no race is saved until the athlete taps Confirm

  Scenario: a race is broken down by seconds to gain
    Given a confirmed race with stations totalling 35:54 and a target of 60:00
    When the athlete opens the race analysis
    Then each of the 8 stations, the runs and Roxzone show seconds to gain
    And they are ordered from most to least

Feature: LLM providers and keys

  Scenario Outline: a skill runs on either provider
    Given a valid <provider> key is saved
    When the athlete runs result-analyzer on <provider>
    Then the run is saved with provider "<provider>" and a model name

    Examples:
      | provider |
      | claude   |
      | gpt      |

  Scenario: missing key blocks a run
    Given a GPT key is saved and no Claude key is saved
    When the athlete runs result-analyzer on claude
    Then the run panel asks for a Claude key
    And no request is sent to any provider

  Scenario: expired key is deleted
    Given a Claude key saved at 2026-11-23 09:00 with 7-day retention
    When the time is 2026-11-30 09:15
    Then no Claude key is stored
    And the audit log has a "keyDeleted" entry
    And the result-analyzer node shows amber for claude

  Scenario: a key is deleted on request
    Given a GPT key is saved with retention "until deleted"
    When the athlete taps Delete key now for gpt
    Then no GPT key is stored
    And the audit log has a "keyDeleted" entry

  Scenario: provider failure leaves no partial result
    Given the Claude API returns HTTP 529
    When the athlete runs result-analyzer on claude
    Then the run shows status "failed" with the provider message
    And no result or session is changed

  Scenario: invalid model output is not saved
    Given the provider returns output missing the required "tips" field twice
    When the athlete runs result-analyzer
    Then the run shows status "failed"
    And nothing is written to results or sessions

  Scenario: cost cap stops runs
    Given a monthly cap of $10 for claude and $10.02 already spent this month
    When the athlete runs result-analyzer on claude
    Then the run is refused with "Monthly cap reached"

Feature: Registry and skills graph

  Scenario: the app pulls the registry by itself
    Given REGISTRY_REF points at a tag whose index.json lists 13 nodes
    When the registry sync runs
    Then the Skills screen shows 13 nodes
    And the weekly-coach agent has 3 numbered steps

  Scenario: registry offline keeps current skills
    Given 13 nodes are loaded
    And GitHub returns HTTP 503
    When the registry sync runs
    Then 13 nodes are still available
    And Settings shows the last successful sync time

  Scenario: invalid registry node is skipped
    Given the index lists a skill whose node.json has no "requires"
    When the registry sync runs
    Then that skill is not loaded
    And the sync report names it
    And every other node loads

  Scenario: hovering an agent shows its run order
    Given the Skills screen is open
    When the athlete hovers weekly-coach
    Then its 3 skills are highlighted and numbered 1 to 3
    And every other node is dimmed

  Scenario: clicking a node opens its run panel
    Given the Skills screen is open
    When the athlete clicks race-analyzer
    Then a panel shows its description, provider choice, credential status and a Run button

Feature: Data in

  Scenario: duplicate Strava event imports once
    Given Strava activity 123456 was imported
    When the Strava webhook sends activity 123456 again
    Then exactly 1 activity 123456 exists

Feature: iPhone app

  Scenario: reinstalled iPhone app shows the same week
    Given the week of 22 Nov 2026 has 6 sessions on the server
    And the iPhone app expired after 7 days
    When the athlete reinstalls it from Xcode and signs in
    Then the Week screen shows the same 6 sessions with their results
