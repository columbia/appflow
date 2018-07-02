Feature: help

    Scenario: see questions
        Given screen is help
        Then see @question

    Scenario: see query
        Given screen is help
        Then see @query

    Scenario: click question to open it
        Given screen is help
        Then click @question
