# Demo walkthrough (about 10 minutes)

Start the portal (`bash start.sh`) and open **http://localhost:8000** in Safari or Chrome on the MacBook.
For a clean run, reset the data first: `cd backend && ../.venv/bin/python -m app.seed --reset`.

Every password is `portal123`. On the login page, click a role chip to fill in its email and password.
Use **Log out** (top right) to switch users, or use a private window for a second user at the same time.

## 1. The problem in one sentence (30 s)

"Marks, labs, faculty presence, opportunities and chat each lived in a different place, or nowhere. This portal puts
them behind one login, with a person in charge of anything that affects grades, bookings or safety."

## 2. Student view: Kavin (2 min)

1. Log in as **Student** (kavin@dept.edu).
2. **Bell:** three unread notifications (marks out, a new internship, ID card approved).
3. **Marks:** each subject shows a chart of Kavin's score against the class average, the question-wise
   breakdown and the weighted internal total ("so far" counts only the tests already held).
4. **Faculty Availability:** shows who is in the department right now (Prof. Arjun is in class, Prof. Rahul is on leave).
5. **Jobs & Internships:** one opening closes in 7 days and is highlighted. Tick **Show expired** to reveal a closed one.
6. The menu has no Lab Booking item: students cannot book labs.

## 3. Teacher view: Prof. Arjun (2 min)

1. Log in as **Teacher** (arjun@dept.edu).
2. **Marks → Enter marks:** he only sees CS501 and CS504, the subjects he holds credentials for.
   - Click **New test**, enter `Quiz 1`, max `5,5`, weightage `5`, then click **Add test**.
   - Type 4 and 3.5 for Kavin. Type **7** for Priya to show the red cell and the refusal on save ("Q1 must be between 0 and 5"), then correct it and save.
   - Click **Export Excel** to download the internal summary and one sheet per test.
3. **Lab Booking:** book **Programming Lab 1** for tomorrow 10:00–11:00. Then try 10:30–12:00 in the same lab: it is
   refused with "already booked … by Prof. Arjun Kumar" (first come, first served).
4. **Faculty Availability:** click **In Class** with the note "Room 204".
5. Log back in as Kavin: the bell shows "CS501 Quiz 1 marks updated: 7.5/10" and the marks page now has a Quiz 1 bar.

## 4. Lab in-charge (1 min)

1. Log in as **Lab In-charge**.
2. Set the lab Arjun booked to **Maintenance**. Its pill turns grey, the lab cannot be booked, and Arjun gets a
   notification that his booking may need to move.

## 5. Verified chat: the security story (3 min)

1. Log in as **aditya@dept.edu** and open **Campus Chat**. He sees "Your ID card is with the department".
2. Log in as **HOD** and open **ID Checks & Reports**. Aditya's ID card photo is shown next to his roll number on record.
   Click **Approve**.
3. Back as Aditya, the bell says he was approved. **Campus Chat → Register this device**: the Mac asks for
   **Touch ID**. That one touch registers the device and unlocks chat for 2 hours.
   - Say: "The fingerprint never leaves the Mac. The browser's WebAuthn API makes the Mac's secure chip sign a challenge,
     and the server only stores a public key."
   - Click **Lock**, then **Unlock with fingerprint** to show unlocking again.
4. In a private window, log in as Kavin, open **Campus Chat**, and click "No fingerprint sensor? Unlock with your password".
   Messages between the two windows appear instantly (WebSockets).
5. As HOD, the reported message "Selling last year's CAT answer scripts" is listed in **ID Checks & Reports**. Click
   **Remove message** and it disappears from everyone's chat at once.

## 6. HOD dashboard (1 min)

Log in as **HOD → HOD Dashboard**:
- Tiles: students, faculty present, labs free, **students at risk** (internal below 50%), open opportunities and items to review.
- Charts: average internal per subject, and lab use this week.
- **Recent activity** shows every action from the demo with who made it and when. **Audit Log** has the full list.

## 7. Questions you may get

- **"Is it secure?"** Passwords are hashed with bcrypt. Every API call carries a signed JWT, and the role is checked on the
  server for every request, not just hidden in the menu. Chat uses ID approval plus WebAuthn, and every change is audit-logged.
- **"What about OCR marks?"** The report's design is in place (a human confirms every mark), but scanning answer
  sheets is future work. Today the teacher types the marks, which is the confirmation step.
- **"Does it scale?"** It runs on PostgreSQL in Docker (`docker compose up`), and the same 29 tests pass on SQLite and PostgreSQL.
- **"Why poll instead of WebSockets everywhere?"** Chat needs instant delivery. The boards are fine at 20 to 30 seconds and stay
  simpler, in line with the report's "keep it simple" principle.
