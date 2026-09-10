# User evaluation protocol

## Objective

Compare the normal EuroLeague website plus YouTube workflow with the project's Video Shots, Play-by-Play, 3D court, and AI Search workflow.

## Participants

Use at least 10 participants when possible. Store a pseudonymous participant ID, not names or email addresses. Record only the broad demographic and experience categories listed in `questions.csv`.

## Procedure

1. Explain the study and obtain consent.
2. Record the demographic/background answers.
3. Ask questions 1-6 first with the EuroLeague website and YouTube, and then with the application. For a less biased comparison, alternate the starting condition between participants.
4. Measure completion time, correctness, and completeness for questions 1-6.
5. For questions 4-6, also record the video timestamp and its absolute difference from the ground truth.
6. Ask questions 7-10 using the 1-5 scale and finish with open question 11.

## Required results

Report task success rate, answer accuracy, median completion time, and median timestamp error separately for the baseline and application. Also report the median/mean response for each 1-5 question and summarize the open comments by theme.

All questions requested by the professor are in `questions.csv`. Store one task or questionnaire response per row in `response_template.csv`.
