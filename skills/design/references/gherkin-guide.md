# Gherkin for acceptance criteria

`docs/acceptance.feature` is the contract `/test` verifies against. Write it so a test can
be written straight from it, without asking you what you meant.

## Shape

```gherkin
Feature: <capability, named after the job it does>

  Scenario: <the specific situation>
    Given <the starting state, concretely>
    When <the single action>
    Then <the observable outcome>
```

## Rules

1. **One action per scenario.** Two `When` steps means two scenarios.
2. **Concrete values, not categories.** `Given 500 transactions` beats `Given many
   transactions`. A test needs a number.
3. **Observable outcomes.** `Then the balance shows 1,240.50` is testable. `Then the data is
   correct` is not.
4. **No implementation.** `When the user taps Save` — not `When saveTransaction() is called`.
   The spec may be implemented differently; the criterion must survive that.
5. **Every failure mode gets a scenario.** If the spec's failure table says "import
   interrupted midway", there is a scenario for it.

## Covering failure, not just success

```gherkin
  Scenario: import is interrupted midway
    Given a CSV of 500 rows
    And the import has processed 200 rows
    When the app is closed
    Then no partial import is visible
    And re-importing the same file produces exactly 500 transactions
```

That last line is the one that catches duplicate-on-retry, which is the defect this
scenario exists to prevent.

## Scenario Outline for the same rule over many values

```gherkin
  Scenario Outline: categorisation applies the first matching rule
    Given a rule "<pattern>" mapping to "<category>"
    When a transaction described "<description>" is imported
    Then its category is "<category>"

    Examples:
      | pattern | category  | description        |
      | TESCO   | Groceries | TESCO STORES 3411  |
      | TFL     | Transport | TFL TRAVEL CHARGE  |
```

## Anti-patterns

| Smell | Why it fails |
|---|---|
| `Then it works` | Nothing to assert |
| `Given the app is set up` | Which state? Tests need the actual precondition |
| Five `And` steps before `When` | The setup is the real subject; split the scenario |
| Scenarios only for the happy path | The judges will ask what happens when it breaks |
