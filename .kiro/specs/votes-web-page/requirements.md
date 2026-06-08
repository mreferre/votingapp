# Requirements Document

## Introduction

This feature adds a dedicated, password-protected web page at the path `/votes` to the existing VotingApp Flask application. Unlike the current API-only endpoints, this page renders a modern HTML interface that displays the four restaurants and their current vote counts in a grid/table layout, and allows an authenticated visitor to cast a vote for a restaurant of their choosing. Votes are persisted using the application's existing Amazon DynamoDB-backed vote logic. After implementation, the feature must be deployed to AWS following the repository's deployment instructions, and the working UI must be validated through browser-based UI tests with screenshots that serve as documented evidence of correct behavior.

## Glossary

- **VotingApp**: The existing single-file Flask web application that stores restaurant votes in Amazon DynamoDB.
- **Votes_Page**: The HTML web page served at the `/votes` route, the subject of this feature.
- **Authentication_Gate**: The component that enforces password protection on the Votes_Page and its supporting page-level endpoints.
- **Vote_Store**: The Amazon DynamoDB table (default name `votingapp-restaurants`) keyed on attribute `name` with vote count attribute `restaurantcount`.
- **Restaurant**: One of the four fixed voting options: `outback`, `bucadibeppo`, `ihop`, `chipotle`.
- **Vote_Count**: The non-negative integer number of votes recorded for a Restaurant in the Vote_Store.
- **Visitor**: A person accessing the Votes_Page through a web browser.
- **Authenticated_Session**: The state in which a Visitor has supplied a valid password and is permitted to view the Votes_Page and cast votes.
- **Configured_Password**: The secret value, supplied through an environment variable, that the Authentication_Gate compares against the password submitted by a Visitor.
- **UI_Test**: A browser-driven automated test that exercises the Votes_Page and captures screenshots.
- **Evidence_Document**: A markdown document in the repository that records UI_Test results and embeds the captured screenshots.
- **Deployment**: The running instance of the VotingApp on AWS App Runner that serves the Votes_Page.

## Requirements

### Requirement 1: Serve the Votes Page

**User Story:** As a Visitor, I want to open a dedicated web page at `/votes`, so that I can view and interact with restaurant voting through a browser instead of calling raw APIs.

#### Acceptance Criteria

1. WHEN a Visitor sends an HTTP GET request to the `/votes` path while holding a valid Authenticated_Session, THE VotingApp SHALL respond within 5 seconds with an HTML document and HTTP status 200.
2. WHEN the VotingApp serves the Votes_Page, THE VotingApp SHALL set the `Content-Type` response header to `text/html`.
3. WHEN the Votes_Page is rendered for an Authenticated_Session, THE Votes_Page SHALL display all four Restaurants (outback, bucadibeppo, ihop, chipotle), each exactly once.
4. THE VotingApp SHALL retain the existing `/`, `/api/outback`, `/api/bucadibeppo`, `/api/ihop`, `/api/chipotle`, `/api/getvotes`, and `/api/getheavyvotes` routes with their current behavior unchanged.
5. IF a Visitor requests a path other than `/votes` for the voting page UI, THEN THE VotingApp SHALL NOT serve the Votes_Page at that path.

### Requirement 2: Password Protection

**User Story:** As an application owner, I want the `/votes` page protected by a password, so that only people who know the password can view vote counts and cast votes.

#### Acceptance Criteria

1. WHEN a Visitor requests the `/votes` path without an Authenticated_Session, THE Authentication_Gate SHALL respond with a password entry form and SHALL NOT include any Vote_Count values or vote-casting controls.
2. WHEN a Visitor submits a non-empty password of up to 256 characters that matches the Configured_Password byte-for-byte (case-sensitive), THE Authentication_Gate SHALL establish an Authenticated_Session and grant access to the Votes_Page.
3. IF a Visitor submits a password that does not match the Configured_Password, THEN THE Authentication_Gate SHALL deny access, SHALL NOT establish an Authenticated_Session, SHALL re-display the password entry form, and SHALL respond with HTTP status 401.
4. WHILE a Visitor lacks an Authenticated_Session, THE Authentication_Gate SHALL reject requests to cast a vote with HTTP status 401 and SHALL NOT modify any Vote_Count.
5. THE Authentication_Gate SHALL read the Configured_Password from an environment variable.
6. IF the Configured_Password environment variable is not set or is empty when the VotingApp starts, THEN THE VotingApp SHALL deny access to the Votes_Page for every Visitor with HTTP status 401.
7. IF a Visitor submits an empty or whitespace-only password, THEN THE Authentication_Gate SHALL deny access and respond with HTTP status 401.

### Requirement 3: Display Vote Counts in a Grid

**User Story:** As a Visitor, I want to see the four restaurants and their vote counts in a grid, so that I can compare current standings at a glance.

#### Acceptance Criteria

1. WHEN the Votes_Page is rendered for an Authenticated_Session, THE Votes_Page SHALL display a grid containing exactly four rows, one row for each of the four Restaurants.
2. WHEN the Votes_Page is rendered for an Authenticated_Session, THE Votes_Page SHALL display the current Vote_Count for each Restaurant as read from the Vote_Store, where each Vote_Count is shown as a non-negative integer (minimum 0).
3. THE Votes_Page SHALL display each Restaurant name as a text label in the same row as that Restaurant's Vote_Count.
4. WHEN a vote is successfully cast, THE Votes_Page SHALL display the updated Vote_Count for the affected Restaurant within 2 seconds and without requiring the Visitor to manually reload the browser.
5. IF the Vote_Store cannot be read when the Votes_Page is rendered, THEN THE Votes_Page SHALL display an error message indicating that vote counts are temporarily unavailable, and SHALL NOT display any partial or stale Vote_Count values.

### Requirement 4: Cast a Vote from the Page

**User Story:** As a Visitor, I want to vote for a restaurant from the page, so that I can register my preference without calling the API directly.

#### Acceptance Criteria

1. WHILE the Votes_Page is loaded, THE Votes_Page SHALL display exactly one vote control for each of the four Restaurants (four vote controls total).
2. WHEN an authenticated Visitor activates the vote control for a Restaurant, THE VotingApp SHALL increment that Restaurant's Vote_Count in the Vote_Store by exactly 1.
3. WHEN a vote increment completes successfully, THE VotingApp SHALL return HTTP status 200 with the updated Vote_Count for the affected Restaurant to the Votes_Page within 3 seconds of the vote control activation.
4. WHEN an authenticated Visitor activates a vote control, THE VotingApp SHALL change only the targeted Restaurant's Vote_Count and leave the other three Restaurants' Vote_Counts unchanged.
5. IF a vote increment fails because the Vote_Store write does not succeed, THEN THE VotingApp SHALL return HTTP status 500, leave all four Restaurants' Vote_Counts unchanged, and THE Votes_Page SHALL display an error message indicating that the vote could not be recorded.
6. IF a vote is requested for a name that is not one of the four Restaurants, THEN THE VotingApp SHALL reject the request with HTTP status 400, leave all four Restaurants' Vote_Counts unchanged, and THE Votes_Page SHALL display an error message indicating that the selected Restaurant is invalid.
7. IF an unauthenticated Visitor activates a vote control, THEN THE VotingApp SHALL reject the request with HTTP status 401 and leave all four Restaurants' Vote_Counts unchanged.

### Requirement 5: Modern, Rich User Interface

**User Story:** As a Visitor, I want the page to look modern and work on my device, so that the experience is pleasant and usable.

#### Acceptance Criteria

1. THE Votes_Page SHALL render its layout without horizontal scrolling of the grid at viewport widths of 360 pixels and 1280 pixels.
2. WHEN a vote is recorded successfully, THE Votes_Page SHALL display a visible confirmation indication within 2 seconds.
3. WHILE a vote request is in progress, THE Votes_Page SHALL display a processing indicator on or near the activated vote control.
4. THE Votes_Page SHALL render the grid, Restaurant labels, Vote_Counts, and vote controls using semantic HTML elements.
5. THE Votes_Page SHALL provide an accessible text label for each vote control identifying the targeted Restaurant for assistive technology.
6. IF a vote request fails, THEN THE Votes_Page SHALL display a visible error indication and SHALL leave the displayed Vote_Counts unchanged.

### Requirement 6: Deploy to AWS

**User Story:** As an application owner, I want the updated application deployed to AWS following the repository's instructions, so that the new page is available in a live environment.

#### Acceptance Criteria

1. WHEN the Deployment is started on AWS App Runner using the repository `apprunner.yaml` configuration (container port 8080), THE Deployment SHALL serve the VotingApp including the `/votes` route and respond with HTTP status 200 at `/votes` for an authenticated request.
2. THE Deployment SHALL set a non-empty Configured_Password environment variable so the Authentication_Gate grants access on a matching credential and denies access on a non-matching or absent credential.
3. THE Deployment SHALL connect to the Vote_Store using `DDB_AWS_REGION` (default us-west-2) and `DDB_TABLE_NAME` (default votingapp-restaurants), and SHALL return current Vote_Counts on the Votes_Page.
4. WHEN an authenticated Visitor requests the Votes_Page on the live Deployment, THE Deployment SHALL serve it over HTTPS and respond within 5 seconds with HTTP status 200.
5. WHERE the DynamoDB table required by the Vote_Store does not yet exist, THE Deployment SHALL be preceded by execution of the repository preparation steps (preparation/prepare.sh) that create and initialize the `votingapp-restaurants` table and the `votingapp-role` IAM role before the App Runner service starts.
6. IF the Vote_Store or its IAM permissions are unavailable, THEN THE Deployment SHALL return an error response for vote operations without exposing internal configuration details.

### Requirement 7: Validate and Document the UI with Screenshots

**User Story:** As an application owner, I want documented evidence that the new page works, so that the work can be confirmed complete.

#### Acceptance Criteria

1. WHEN the UI_Test starts, THE UI_Test SHALL navigate to the Votes_Page of the live Deployment in a web browser and SHALL confirm the page has fully rendered within 30 seconds.
2. IF the Votes_Page does not respond or fully render within 30 seconds, THEN THE UI_Test SHALL record a load failure in the Evidence_Document and SHALL halt remaining steps.
3. WHEN an unauthenticated Visitor requests the Votes_Page, THE UI_Test SHALL capture a screenshot image showing the password prompt before any Vote_Count is displayed.
4. WHEN authentication succeeds, THE UI_Test SHALL capture a screenshot image of the Votes_Page grid showing exactly four Restaurants, each with its corresponding Vote_Count value visible.
5. WHEN a single vote is cast for a Restaurant, THE UI_Test SHALL capture a screenshot image showing that Restaurant's Vote_Count increased by exactly 1 relative to the value recorded before the vote.
6. THE Evidence_Document SHALL embed each captured screenshot image and SHALL record, for each UI_Test step, a pass or fail status together with the observed outcome.
7. IF any UI_Test step fails to demonstrate the expected behavior, THEN THE Evidence_Document SHALL record the specific step, the expected behavior, and the observed behavior, AND the work SHALL NOT be considered complete.
8. THE Evidence_Document SHALL be stored as a markdown file within the repository.
