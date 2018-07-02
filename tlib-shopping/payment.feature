Feature: payment
    # Card info input tests
    Scenario: fill in card no
        Given screen is cardedit
        And cardno_filled is false
        When text @card_no '@card_no'
        Then set cardno_filled to true
        And screen is cardedit

    Scenario: fill in card exp [mm/yy]
        Given screen is cardedit
        And cardexp_filled is false
        When text @card_exp '@card_exp'
        Then set cardexp_filled to true
        And screen is cardedit

    Scenario: fill in card exp [separate]
        Given screen is cardedit
        And cardexp_filled is false
        When select @card_year '@card_year'
        And select @card_month '@card_month'
        Then set cardexp_filled to true
        And screen is cardedit

    Scenario: fill in card cvc
        Given screen is cardedit
        And cardcvc_filled is false
        When text @card_cvv '@card_cvv'
        Then set cardcvc_filled to true
        And screen is cardedit

    Scenario: fill in card name
        Given screen is cardedit
        And cardname_filled is false
        When text @card_name '@card_name'
        Then set cardname_filled to true
        And screen is cardedit

    Scenario: save card info [no+exp+cvc]
        Given screen is cardedit
        And cardno_filled is true
        And cardexp_filled is true
        And cardcvc_filled is true
        When click @card_save
        Then screen is not cardedit

    Scenario: save card info [no+exp+cvc+name]
        Given screen is cardedit
        And cardno_filled is true
        And cardexp_filled is true
        And cardcvc_filled is true
        And cardname_filled is true
        When click @card_save
        Then screen is not cardedit

    Scenario: save card when info is not filled
        Given screen is cardedit
        And cardno_filled is false
        When click @card_save
        Then screen is cardedit


    # Payment options tests
    Scenario: add card
        Given screen is payment
        When click @card_new
        Then screen is cardedit

    Scenario: delete card
        Given screen is payment
        When click @card_delete
        Then screen is payment

    Scenario: select card
        Given screen is payment
        Then click @card_select
        And click @continue

    Scenario: see card
        Given screen is payment
        Then see @card
