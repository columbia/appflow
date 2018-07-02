Feature: textsize
    Scenario: smaller text
        Given screen is textsize
        When click @smaller

    Scenario: larger text
        Given screen is textsize
        When click @larger
        Then screen is not textsize

    Scenario: smaller text [with apply]
        Given screen is textsize
        When click @smaller
        And click @apply
        Then screen is not textsize

    Scenario: larger text [with apply]
        Given screen is textsize
        When click @larger
        And click @apply
        Then screen is not textsize
