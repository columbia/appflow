Feature: welcome

    @registerX
    Scenario: sign up
        Given screen is welcome
        When click @signup
        Then screen is register

    @signinX
    Scenario: sign in
        Given screen is welcome
        When click @existing
        Then screen is signin

    @mainX
    Scenario: skip sign in / sign up
        Given screen is welcome
        When click @skip
        Then screen is not welcome

    Scenario: pass intro
        Given screen is app_intro
        Then click @pass_intro

    Scenario: pass intro
        Given screen is app_intro2
        Then click @pass_intro2

    Scenario: continue with google
        Given screen is welcome
        Then see @google

    Scenario: continue with facebook
        Given screen is welcome
        Then see @facebook
