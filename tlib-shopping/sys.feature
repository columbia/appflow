Feature: sys

    Scenario: allow permission
        Given screen is sys_permission
        Then click @sys_permission_allow

    Scenario: ignore current accounts
        Given screen is sys_accounts
        Then click @sys_accounts_cancel

    Scenario: disallow notifications
        Given screen is sys_notification
        Then click !marked:'NO'

    Scenario: disallow notifications
        Given screen is sys_notification2
        Then click !marked:'Cancel'

    Scenario: disallow notifications
        Given screen is sys_notification3
        Then click !marked:'Don't Allow'

    Scenario: skip any prompt
        Given screen is sys_prompt
        Then click !marked:'no thanks'

    Scenario: skip any prompt
        Given screen is sys_prompt2
        Then click !marked:'Cancel'

    Scenario: skip any prompt
        Given screen is sys_prompt3
        Then click !Button+marked:'NO, THANK YOU'

    Scenario: don't save in smartlock
        Given screen is sys_smartlock
        Then click !marked:'credential_save_reject'

    Scenario: accept tos
        Given screen is sys_termofuse
        Then click !marked:'Agree'

    Scenario: accept tos
        Given screen is sys_termofuse2
        Then click !marked:'ACCEPT'

    Scenario: accept message
        Given screen is app_message
        Then click @app_message_accept

    Scenario: accept message
        Given screen is app_message2
        Then click @app_message_continue

    Scenario: loading please wait
        Given screen is app_wait
        Then wait 10
