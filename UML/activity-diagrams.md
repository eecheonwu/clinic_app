# UML Activity Diagrams

## 1. Booking Request & Restriction Validation Flow

Details the step-by-step control logic executed by the scheduling engine when a booking request arrives (**FR-003**, **FR-015**, **FR-019** of [Product Requirements](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/product/requirements.md)).

```mermaid
flowchart TD
    Start([Start Booking Flow]) --> SelectDetails[Select Branch, Doctor, Date & Time]
    SelectDetails --> CheckTier{Check Patient Penalty Tier}
    
    CheckTier -->|Tier 3: Restricted| IsStaff{Is Requester Clinic Staff?}
    IsStaff -->|Yes| OverrideChecked{Override Option Selected?}
    OverrideChecked -->|Yes| LogOverride[Log Admin Override to Audit Trail] --> VerifyShift
    OverrideChecked -->|No| BlockBooking[Show Error: Override Required] --> EndBooking([End])
    IsStaff -->|No| BlockSelfService[Block Online Booking. Prompt contact clinic] --> EndBooking
    
    CheckTier -->|Tier 2: Soft Flag| WarnSoft[Display Warning Flag] --> ConfirmBooking{Confirm Booking?}
    ConfirmBooking -->|Yes| VerifyShift
    ConfirmBooking -->|No| CancelRequest[Cancel Request] --> EndBooking

    CheckTier -->|Normal / Tier 1| VerifyShift{Doctor has Availability Shift?}
    
    VerifyShift -->|No| BlockAvailability[Show Error: Doctor Unavailable] --> EndBooking
    VerifyShift -->|Yes| AcquireLock[Acquire Pessimistic DB Lock on Shift & Slots]
    
    AcquireLock --> CheckConflict{Conflicting Appointment Exists?}
    CheckConflict -->|Yes| BlockConflict[Show Error: Slot No Longer Available] --> EndBooking
    CheckConflict -->|No| CreateAppt[Create Appointment with status='booked']
    
    CreateAppt --> EnqueueAlert[Enqueue Notification Task in Redis]
    EnqueueAlert --> SuccessBooking[Display Confirmation] --> EndBooking
```

---

## 2. Cancellation Penalty Engine Control Flow

Details the business rules processed by the system when an appointment is cancelled (**FR-012** to **FR-017** of [Product Requirements](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/product/requirements.md)).

```mermaid
flowchart TD
    Start([Start Cancellation Request]) --> IdentifyRequester{Who Initiated Cancellation?}
    
    IdentifyRequester -->|Clinic / Doctor| ClinicExempt[Mark as Clinic-Initiated Exemption] --> DoCancel[Cancel Appointment & Release Slot]
    IdentifyRequester -->|Patient| CheckTime{Time until Appointment Starts}
    
    CheckTime -->|>= 2 Hours| DoCancel
    CheckTime -->|< 2 Hours| CheckEmergency{Marked as Emergency?}
    
    CheckEmergency -->|Yes| LogEmergency[Log Emergency Exemption] --> DoCancel
    CheckEmergency -->|No| LogPenalty[Log Late Cancellation Incident on Patient Profile]
    
    LogPenalty --> CountIncidents[Count Late Cancel/No-show incidents in rolling 90 days]
    CountIncidents --> UpdateTier{Update Patient Penalty Tier}
    
    UpdateTier -->|1 Incident| SetTier1[Set Penalty Tier = Tier 1 Warning] --> DoCancel
    UpdateTier -->|2-3 Incidents| SetTier2[Set Penalty Tier = Tier 2 Soft Flag] --> DoCancel
    UpdateTier -->|>= 4 Incidents| SetTier3[Set Penalty Tier = Tier 3 Restricted] --> DoCancel
    
    DoCancel --> EnqueueNotification[Enqueue Cancellation Alert to Task Queue]
    EnqueueNotification --> Success([End])
```
