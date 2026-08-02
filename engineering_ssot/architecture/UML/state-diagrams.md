# UML State Diagrams

## 1. Appointment & Payment State Machine

Maps out status and payment transitions for the main scheduling unit (**DR-004**, **INT-005** of [Product Requirements](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/product/requirements.md)).

```mermaid
stateDiagram-v2
    [*] --> Booked_Pending : Patient/Staff Books Appointment
    
    state Booked_Pending {
        [*] --> Status_Booked
        [*] --> Payment_Pending
    }

    state Cancelled {
        [*] --> Status_Cancelled
        state "Payment Processed / Waived" as Pay_Proc
    }

    state Completed {
        [*] --> Status_Completed
        state "Fully Paid / Waived" as Pay_Done
    }

    state NoShow {
        [*] --> Status_NoShow
        state "Late/No-Show Penalty Applied" as Pen_App
    }

    Booked_Pending --> Cancelled : Cancelled > 2h before (Normal Cancellation)
    Booked_Pending --> Cancelled : Cancelled < 2h before (Late Cancellation - Penalty logged)
    Booked_Pending --> Completed : Doctor submits consultation log (FR-006)
    Booked_Pending --> NoShow : Patient fails to arrive (No-show - Penalty logged)

    Completed --> [*]
    Cancelled --> [*]
    NoShow --> [*]
```

---

## 2. Patient Penalty & Booking Restriction Lifecycle

Shows how late cancellations and no-shows affect patient booking permissions in rolling 90-day windows (**FR-012**, **FR-013**, **FR-014** of [Product Requirements](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/product/requirements.md)).

```mermaid
stateDiagram-v2
    [*] --> Normal : New Patient Account Registered
    
    Normal --> Tier1_Warning : 1st Late Cancel / No-show
    Tier1_Warning --> Tier2_SoftFlag : 2nd-3rd Late Cancel / No-show
    Tier2_SoftFlag --> Tier3_Restricted : >= 4th Late Cancel / No-show
 
    Tier3_Restricted --> Tier2_SoftFlag : rolling 90 days elapse for older incidents
    Tier2_SoftFlag --> Tier1_Warning : rolling 90 days elapse for older incidents
    Tier1_Warning --> Normal : rolling 90 days elapse for older incidents

    state Normal {
        Note: Full self-service online booking enabled
    }
    state Tier1_Warning {
        Note: Warning banner shown on booking/cancellation screen
    }
    state Tier2_SoftFlag {
        Note: Soft flag on profile; requires confirmation to schedule
    }
    state Tier3_Restricted {
        Note: Online booking BLOCKED. Requires receptionist manual override.
    }

---

## 3. Email Verification Token Lifecycle State Machine

Maps out token states during email registration and verification (**ADR-005**).

```mermaid
stateDiagram-v2
    [*] --> Token_Issued : Patient registers via email (token_hash created, TTL 60m)

    Token_Issued --> Verification_Success : Link clicked & valid password set (is_used = TRUE)
    Token_Issued --> Expired : 60-minute TTL elapses (expires_at reached)
    Token_Issued --> Superseded : New registration/resend requested (is_expired = TRUE)
    Token_Issued --> Invalidated : Max 5 failed password attempts

    Verification_Success --> User_Activated : User row created (is_email_verified = TRUE)
    User_Activated --> [*]

    Expired --> Resend_Prompt : Patient requests new link
    Superseded --> Resend_Prompt
    Invalidated --> Resend_Prompt

    Resend_Prompt --> Token_Issued : New token generated (Rate limit <= 3 per 15m)
```
```
