The flow
1. Upload.
The candidate uploads Aadhaar, PAN, 10th and 12th marksheets, semester marksheets and the degree certificate. Each can be a PDF, PNG or JPG. They can also take a selfie, which is optional. The system also receives the candidate's resume details and interview data from the earlier stages of the hiring pipeline.

2. Basic file check.
Each file is checked to make sure it's a real PDF/PNG/JPG (by looking inside the file, not trusting the name), not empty, not corrupted, not larger than 15 MB, and not a PDF longer than 10 pages. A file that fails is rejected. PDFs are then converted into page images so every document can be handled the same way.

3. Quality gate.
Each document image is checked for blur, darkness, glare and very low resolution. If it fails any of these, it's rejected and the candidate is asked to upload it again. Nothing else happens to it. The selfie skips this step.

4. OCR.
The text is read from every document that passed, along with where each word sits on the page. The selfie skips this step.

5. Classification.
Using the OCR text, the system decides what each document is: Aadhaar, PAN, 10th marksheet, 12th marksheet, semester marksheet or degree certificate. It looks for words like "Income Tax Department", "UIDAI", "Senior School Certificate" or "Bachelor of", and for patterns like a PAN or Aadhaar number. It also checks that none of the required documents are missing.

6. Extraction.
The system pulls out the useful information from each document:

Fields: name, date of birth, father's name, Aadhaar/PAN number, university or board, degree, year, roll number, each subject's marks, total, percentage/CGPA, result
QR code: reads the QR and, for Aadhaar, decodes the details UIDAI stored in it
Photo: crops the face from the Aadhaar and PAN
File details: which software created the file, whether it was edited after creation, which fonts it uses
Steps 1–6 are built. Everything below is planned but not built yet.

7. Checking each document on its own.

Is the Aadhaar number mathematically valid, and does the QR match what's printed on the card? Is the PAN number in the right format? (F1)
Do the marks on the marksheet add up to the printed total? (F7')
Was the file edited in software like Photoshop or Canva? (F8)
Has any part of the image been edited, like a changed mark or DOB? (F9)
Is the university or board real and recognised? (F5)
8. Checking the documents against each other and against the candidate.

Are the name and DOB the same on every document? (F2)
Do the degree, marks and years match the resume? (F3)
Do the dates make sense: 10th, then 12th, then degree? (F4)
Is the person in the Aadhaar and PAN photos the same, and does the selfie match them (if there is one)? (F11)
Taking all the evidence together, does a document look completely fake or AI-generated? (F12)
9. Scoring.
Every problem found counts toward a risk score. Some problems are serious enough to decide the outcome alone, such as an invalid Aadhaar QR signature or a university on the UGC fake list. When several problems point at the same document, that raises confidence it's fraudulent. Each document, and the candidate overall, gets PASS, REVIEW or REJECT (suggested).

10. Result.

PASS: onboarding continues automatically.
REVIEW / REJECT: HR sees the document, what was found, the reasons, and highlighted evidence. A person always makes the final decision. The Aadhaar number stays hidden unless that Aadhaar was flagged.
11. Saving (not built yet).
The extracted text, fields, results and HR's decision get stored in a database, so there's a record for audits and disputes.

Status: steps 1–6 are working and tested on synthetic documents. Steps 7–11 are next, starting with F1 and F7'.