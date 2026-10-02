import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { relayApi } from './api';
import { accessToken, cognitoEnabled, completeSignIn, currentSubject, localSubject, setLocalSubject, signOut, startSignIn } from './auth';
import type {
  AssistanceRequest,
  CreateRequestInput,
  RequestCategory,
  RequestStatus,
  RequestUrgency,
  StructuredRequest,
  Volunteer,
  VolunteerMatch,
  CommunityProfile,
} from './api';

const urgencyLabels: Record<RequestUrgency, string> = {
  normal: 'Whenever possible',
  high: 'Soon',
  urgent: 'Urgent',
};

type RequestCardData = AssistanceRequest & { matches?: VolunteerMatch[] };

const activeRequestStatuses = new Set([
  'REQUESTED',
  'CLAIMED',
  'IN_PROGRESS',
  'VOLUNTEER_COMPLETED',
  'REQUESTER_CONFIRMED',
]);
const pastRequestStatuses = new Set(['RESOLVED', 'CANCELLED', 'CANCELED', 'CLOSED']);

function App() {
  const [requests, setRequests] = useState<RequestCardData[]>([]);
  const [volunteers, setVolunteers] = useState<Volunteer[]>([]);
  const [selectedVolunteerId, setSelectedVolunteerId] = useState('local-requester');
  const [selectedRequestId, setSelectedRequestId] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingMatchesFor, setLoadingMatchesFor] = useState('');
  const [understanding, setUnderstanding] = useState<StructuredRequest | null>(null);
  const [description, setDescription] = useState('');
  const [locationLabel, setLocationLabel] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [peopleOverride, setPeopleOverride] = useState('');
  const [structuring, setStructuring] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [profile, setProfile] = useState<CommunityProfile | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authError, setAuthError] = useState('');
  const [demoOpen, setDemoOpen] = useState(false);
  const cognitoConfigured = cognitoEnabled();

  const activeVolunteer = useMemo(
    () => volunteers.find((volunteer) => volunteer.id === selectedVolunteerId),
    [selectedVolunteerId, volunteers],
  );
  const activeRequests = requests.filter((request) => activeRequestStatuses.has(request.status));
  const pastRequests = requests.filter((request) => pastRequestStatuses.has(request.status));

  const loadData = useCallback(async () => {
    setError('');
    try {
      const [loadedRequests, loadedVolunteers] = await Promise.all([
        relayApi.listRequests(),
        relayApi.listVolunteers(),
      ]);
      setRequests(loadedRequests);
      setVolunteers(loadedVolunteers);
      try {
        setProfile(await relayApi.getProfile());
      } catch {
        setProfile(null);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load the community board.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void completeSignIn()
      .catch((cause) => setAuthError(cause instanceof Error ? cause.message : 'Sign-in failed.'))
      .finally(() => setAuthReady(true));
  }, []);

  useEffect(() => {
    if (!cognitoConfigured) setLocalSubject('local-requester');
  }, [cognitoConfigured]);

  useEffect(() => {
    if (!authReady || (cognitoConfigured && !accessToken())) return;
    void loadData();
  }, [loadData, authReady, cognitoConfigured]);

  async function handleSaveProfile(name: string, roles: CommunityProfile['roles']) {
    setError('');
    try {
      const saved = await relayApi.saveProfile({ name, roles });
      setProfile(saved);
      setNotice('Your Relay profile is ready. Email verification confirms account access, not the truth of any request.');
      await loadData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save your profile.');
    }
  }

  async function handleUnderstand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setNotice('');
    setStructuring(true);
    try {
      const draft = await relayApi.structureRequest(description.trim());
      setUnderstanding(draft);
      setPeopleOverride('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Relay could not structure this request.');
    } finally {
      setStructuring(false);
    }
  }

  async function handleConfirm() {
    if (!understanding) return;
    setError('');
    setNotice('');
    if (Boolean(latitude.trim()) !== Boolean(longitude.trim())) {
      setError('Enter both coordinates to include distance in matching, or leave both blank.');
      return;
    }
    setCreating(true);
    const location: CreateRequestInput['location'] = {
      label: locationLabel.trim() || 'Location not shared',
    };
    if (latitude.trim() && longitude.trim()) {
      location.latitude = Number(latitude);
      location.longitude = Number(longitude);
    }
    const input: CreateRequestInput = {
      description: description.trim(),
      category: understanding.category,
      urgency: understanding.urgency,
      location,
      peopleAffected: peopleOverride ? Number(peopleOverride) : understanding.peopleAffected,
      requiredSkills: understanding.requiredSkills,
      mobilityNeeds: understanding.mobilityNeeds,
      summary: understanding.summary,
    };

    try {
      const created = await relayApi.createRequest(input);
      setRequests((current) => [created, ...current]);
      setSelectedRequestId(created.id);
      setUnderstanding(null);
      setNotice('Request confirmed. Finding people who can help…');
      setLoadingMatchesFor(created.id);
      const matches = await relayApi.findMatches(created.id);
      const refreshed = await relayApi.getRequest(created.id);
      setRequests((current) => current.map((item) => item.id === created.id ? { ...refreshed, matches } : item));
      setNotice(matches.length ? 'Your request is ready to meet a helpful neighbor.' : 'Your request is posted. No available matches yet.');
      setDescription('');
      setLocationLabel('');
      setLatitude('');
      setLongitude('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not finish creating your request.');
    } finally {
      setLoadingMatchesFor('');
      setCreating(false);
    }
  }

  async function handleFindMatches(requestId: string) {
    setError('');
    setNotice('');
    setSelectedRequestId(requestId);
    setLoadingMatchesFor(requestId);
    try {
      const matches = await relayApi.findMatches(requestId);
      const refreshed = await relayApi.getRequest(requestId);
      setRequests((current) => current.map((item) => item.id === requestId ? { ...refreshed, matches } : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not find volunteer matches.');
    } finally {
      setLoadingMatchesFor('');
    }
  }

  async function handleClaim(requestId: string, volunteerId: string) {
    setError('');
    try {
      if (!cognitoConfigured) setLocalSubject(volunteerId);
      const updated = await relayApi.claimRequest(requestId);
      setSelectedVolunteerId(volunteerId);
      setRequests((current) => current.map((item) => item.id === requestId ? { ...item, ...updated } : item));
      setSelectedRequestId(requestId);
      setVolunteers(await relayApi.listVolunteers());
      setNotice('A neighbor has claimed this request.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not claim this request.');
    }
  }

  async function handleStatus(requestId: string, status: RequestStatus) {
    setError('');
    try {
      if (!cognitoConfigured && selectedVolunteerId) setLocalSubject(selectedVolunteerId);
      const updated = await relayApi.updateStatus(requestId, status);
      setRequests((current) => current.map((item) => item.id === requestId ? { ...item, ...updated } : item));
      setVolunteers(await relayApi.listVolunteers());
      setNotice(status === 'VOLUNTEER_COMPLETED' ? 'The requester can now confirm the help was received.' : 'Request status updated.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update the request.');
    }
  }

  async function handleConfirmReceived(requestId: string) {
    setError('');
    try {
      if (!cognitoConfigured) {
        setLocalSubject('local-requester');
        setSelectedVolunteerId('local-requester');
      }
      const updated = await relayApi.confirmRequest(requestId);
      setRequests((current) => current.map((item) => item.id === requestId ? { ...item, ...updated } : item));
      setNotice('Thanks for confirming that help was received.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not confirm this request.');
    }
  }

  async function handleReport(targetType: 'REQUEST' | 'USER', targetId: string) {
    try {
      await relayApi.report(targetType, targetId, 'other', '');
      setNotice('Thanks for raising this. Your report was saved for review.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not submit the report.');
    }
  }

  async function handleBlock(requestId: string, userId: string) {
    try {
      await relayApi.blockUser(userId);
      window.dispatchEvent(new Event('relay-blocks-updated'));
      setNotice('This account will no longer be considered for your matches.');
      await handleFindMatches(requestId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not block this account.');
    }
  }

  function resetDraft() {
    setUnderstanding(null);
    setError('');
  }

  function requestBrowserLocation(onLocation: (latitude: number, longitude: number) => void) {
    if (!navigator.geolocation) {
      setError('This browser does not support location sharing. You can enter a neighborhood instead.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => onLocation(position.coords.latitude, position.coords.longitude),
      () => setError('Location was not shared. You can enter a neighborhood and continue without coordinates.'),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  }

  if (!authReady) {
    return <div className="auth-screen"><div className="state-card" role="status"><span className="spinner" />Preparing Relay…</div></div>;
  }
  if (cognitoConfigured && !accessToken()) {
    if (demoOpen) return <DemoWalkthrough onExit={() => setDemoOpen(false)} />;
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <a className="brand" href="#top"><span className="brand-mark">r</span><span>relay</span></a>
          <p className="section-kicker">NEIGHBORS HELPING NEIGHBORS</p>
          <h1>A little help goes a long way.</h1>
          <p>Sign in or create an account. Email verification confirms access to your account; it does not verify the truth of a request.</p>
          {authError && <p className="error-message" role="alert">{authError}</p>}
          <button className="submit-button" type="button" onClick={() => void startSignIn()}>Continue to sign in or register <span>→</span></button>
          <button className="demo-entry-button" type="button" onClick={() => setDemoOpen(true)}>Try the demo <span aria-hidden="true">→</span></button>
          <p className="safety-notice">For immediate danger, contact local emergency services. Relay is not an emergency service.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Relay home">
          <span className="brand-mark" aria-hidden="true">r</span><span>relay</span>
        </a>
        <p className="header-message">Neighbors helping neighbors.</p>
        {cognitoConfigured ? (
          <div className="account-controls"><span>{profile?.name || 'Your account'}</span><button className="text-button" type="button" onClick={signOut}>Sign out</button></div>
        ) : (
          <div className="volunteer-preview">
            <label htmlFor="volunteer-select">Local demo view</label>
            <select id="volunteer-select" value={selectedVolunteerId} onChange={(event) => { setSelectedVolunteerId(event.target.value); setLocalSubject(event.target.value); void loadData(); }}>
              <option value="local-requester">Requester demo</option>
              {volunteers.filter((item) => item.role === 'VOLUNTEER').map((volunteer) => (
                <option key={volunteer.id} value={volunteer.id}>{volunteer.name}{volunteer.availability === 'OFFLINE' ? ' · offline' : ''}</option>
              ))}
            </select>
          </div>
        )}
      </header>

      <main id="top">
        <section className="welcome">
          <div>
            <p className="eyebrow"><span className="eyebrow-star">✳</span> A little help goes a long way</p>
            <h1>When we show up,<br /><em>we move forward.</em></h1>
            <p className="welcome-copy">Ask for the help you need. Your neighbors are ready to lend a hand.</p>
          </div>
          <div className="welcome-note"><span aria-hidden="true">✳</span><p>Small acts<br />make a strong<br /><em>community.</em></p></div>
        </section>

        {error && <div className="global-message error-message" role="alert">{error}<button type="button" onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
        {notice && <div className="global-message success-message" role="status">{notice}<button type="button" onClick={() => setNotice('')} aria-label="Dismiss message">×</button></div>}

        <div className="safety-notice" role="note">Relay coordinates everyday community assistance. If anyone is in immediate danger, contact local emergency services first. Relay cannot verify whether a request is true.</div>

        <div className="content-grid">
          <section className="panel form-panel" aria-labelledby="form-title">
            {!profile ? <ProfileSetup onSave={(name, roles) => void handleSaveProfile(name, roles)} /> : !understanding ? (
              <>
                <div className="panel-heading">
                  <div className="section-icon" aria-hidden="true">＋</div>
                  <div><p className="section-kicker">LET’S GET YOU SUPPORT</p><h2 id="form-title">Ask for help</h2></div>
                </div>
                <p className="panel-intro">Describe what would make today a little easier. You can review the details before sharing.</p>
                <p className="field-hint">Your confirmed request is visible to signed-in community members. Keep details free of addresses and phone numbers; the full description stays visible only to you.</p>
                <form onSubmit={handleUnderstand}>
                  <label htmlFor="description">What do you need help with?</label>
                  <textarea id="description" name="description" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="My elderly parents need someone to pick up their prescription…" maxLength={1000} required />
                  {looksLikeEmergency(description) && <div className="safety-notice emergency-notice" role="alert">This wording may describe immediate danger. Relay cannot assess emergencies. Contact local emergency services now if anyone may be at risk.</div>}
                  <div className="form-row location-row">
                    <div className="field-group">
                      <label htmlFor="location">Neighborhood or landmark <span className="optional">OPTIONAL</span></label>
                      <input id="location" name="location" value={locationLabel} onChange={(event) => setLocationLabel(event.target.value)} type="text" placeholder="e.g. Block C" maxLength={120} />
                      <span className="field-hint">A general area is enough; no exact address needed.</span>
                    </div>
                  </div>
                  <details className="coordinate-details">
                    <summary>Share approximate location for distance matching (optional)</summary>
                    <p className="field-hint">Relay asks your browser only after you click. Coordinates are rounded before storage and never shown to other users; a neighborhood label is enough.</p>
                    <button className="quiet-action" type="button" onClick={() => requestBrowserLocation((lat, lon) => { setLatitude(String(lat)); setLongitude(String(lon)); })}>Use my approximate location</button>
                    <div className="form-row coordinate-row">
                      <div className="field-group"><label htmlFor="latitude">Latitude</label><input id="latitude" type="number" step="any" value={latitude} onChange={(event) => setLatitude(event.target.value)} placeholder="17.4000" /></div>
                      <div className="field-group"><label htmlFor="longitude">Longitude</label><input id="longitude" type="number" step="any" value={longitude} onChange={(event) => setLongitude(event.target.value)} placeholder="78.4000" /></div>
                    </div>
                    <span className="field-hint">Relay uses straight-line distance only. Leave both blank if you prefer.</span>
                  </details>
                  <button className="submit-button" type="submit" disabled={structuring}>
                    {structuring ? 'Understanding your request…' : 'Review request'} <span aria-hidden="true">→</span>
                  </button>
                  <p className="privacy-note"><span aria-hidden="true">⌑</span> Nothing is shared until you confirm.</p>
                </form>
              </>
            ) : (
              <>
                <div className="panel-heading review-heading">
                  <div className="section-icon review-icon" aria-hidden="true">✳</div>
                  <div><p className="section-kicker">REQUEST DRAFT</p><h2 id="form-title">Relay understood this as</h2></div>
                  <button className="text-button" type="button" onClick={resetDraft}>Edit</button>
                </div>
                <p className="understood-summary">“{understanding.summary}”</p>
                <dl className="understanding-grid">
                  <div><dt>Category</dt><dd>{titleCase(understanding.category)}</dd></div>
                  <div><dt>Urgency</dt><dd>{urgencyLabels[understanding.urgency]}</dd></div>
                  <div><dt>People affected</dt><dd><input aria-label="People affected" type="number" min="1" max="1000" placeholder={String(understanding.peopleAffected)} value={peopleOverride} onChange={(event) => setPeopleOverride(event.target.value)} /></dd></div>
                  <div><dt>Mobility</dt><dd>{titleCase(understanding.mobilityNeeds)}</dd></div>
                  <div className="understanding-wide"><dt>Skills needed</dt><dd className="skill-chips">{understanding.requiredSkills.map((skill) => <span key={skill}>{formatSkill(skill)}</span>)}</dd></div>
                </dl>
                <div className="original-description"><span>Your words</span><p>{description}</p></div>
                <button className="submit-button" type="button" onClick={() => void handleConfirm()} disabled={creating}>
                  {creating ? 'Creating request…' : 'Confirm request'} <span aria-hidden="true">→</span>
                </button>
                <p className="privacy-note"><span aria-hidden="true">⌑</span> You can edit this draft before it reaches the community.</p>
              </>
            )}
            {profile?.roles.includes('VOLUNTEER') && <VolunteerProfileEditor onError={setError} onNotice={setNotice} />}
            {profile && <BlockSettings onNotice={setNotice} onError={setError} />}

          </section>

          <section className="requests-column" aria-labelledby="requests-title">
            <div className="requests-heading">
              <div><p className="section-kicker">NEIGHBORS SHOWING UP</p><h2 id="requests-title">Community requests <span className="count-pill">{activeRequests.length}</span></h2></div>
              <button className="refresh-button" type="button" onClick={() => void loadData()} aria-label="Refresh community board">↻</button>
            </div>
            <p className="requests-subtitle">Helping one another, one small thing at a time.</p>
            {loading ? (
              <div className="state-card" role="status"><span className="spinner" />Loading community requests…</div>
            ) : error && activeRequests.length === 0 && pastRequests.length === 0 ? (
              <div className="state-card state-error"><p>{error}</p><button type="button" onClick={() => void loadData()}>Try again</button></div>
            ) : activeRequests.length === 0 ? (
              <div className="state-card empty-state"><span className="empty-icon">✳</span><strong>It’s quiet here for now.</strong><span>{pastRequests.length > 0 ? 'There are no current requests. Past requests are below.' : 'When someone asks for help, you’ll see it here.'}</span></div>
            ) : (
              <div className="request-list" aria-live="polite">
                {activeRequests.map((request) => (
                  <RequestCard
                    key={request.id}
                    request={request}
                    volunteer={activeVolunteer}
                    viewerId={cognitoConfigured ? currentSubject() || '' : selectedVolunteerId || localSubject()}
                    localDemo={!cognitoConfigured}
                    finding={loadingMatchesFor === request.id}
                    selected={selectedRequestId === request.id}
                    onFindMatches={() => void handleFindMatches(request.id)}
                    onClaim={(volunteerId) => void handleClaim(request.id, volunteerId)}
                    onStatus={(status) => void handleStatus(request.id, status)}
                    onConfirmReceived={() => void handleConfirmReceived(request.id)}
                    onReport={() => void handleReport('REQUEST', request.id)}
                    onBlock={(userId) => void handleBlock(request.id, userId)}
                    onReportUser={(userId) => void handleReport('USER', userId)}
                  />
                ))}
              </div>
            )}
            {!loading && pastRequests.length > 0 && (
              <details className="past-requests">
                <summary>Past requests <span className="count-pill">{pastRequests.length}</span></summary>
                <div className="request-list" aria-live="polite">
                  {pastRequests.map((request) => (
                    <RequestCard
                      key={request.id}
                      request={request}
                      volunteer={activeVolunteer}
                      viewerId={cognitoConfigured ? currentSubject() || '' : selectedVolunteerId || localSubject()}
                      localDemo={!cognitoConfigured}
                      finding={loadingMatchesFor === request.id}
                      selected={selectedRequestId === request.id}
                      onFindMatches={() => void handleFindMatches(request.id)}
                      onClaim={(volunteerId) => void handleClaim(request.id, volunteerId)}
                      onStatus={(status) => void handleStatus(request.id, status)}
                      onConfirmReceived={() => void handleConfirmReceived(request.id)}
                      onReport={() => void handleReport('REQUEST', request.id)}
                      onBlock={(userId) => void handleBlock(request.id, userId)}
                      onReportUser={(userId) => void handleReport('USER', userId)}
                    />
                  ))}
                </div>
              </details>
            )}
          </section>
        </div>
      </main>

      <footer className="footer"><span>Small acts. Stronger communities.</span><span>For immediate danger, contact your local emergency services.</span></footer>
    </div>
  );
}

const demoStages = ['ASK', 'MATCH', 'ACT', 'RESOLVE'] as const;

function DemoWalkthrough({ onExit }: { onExit: () => void }) {
  const [stageIndex, setStageIndex] = useState(0);
  const stage = demoStages[stageIndex];

  return (
    <main className="demo-screen">
      <header className="demo-topbar">
        <a className="brand" href="#demo-top" aria-label="Relay demo home">
          <span className="brand-mark" aria-hidden="true">r</span><span>relay</span>
        </a>
        <button className="text-button" type="button" onClick={onExit}>Back to Relay</button>
      </header>
      <section className="demo-card" id="demo-top" aria-labelledby="demo-title">
        <div className="demo-heading">
          <div>
            <p className="section-kicker">INTERACTIVE DEMO</p>
            <h1 id="demo-title">A little help, from ask to resolved.</h1>
            <p>Follow one community request through Relay’s coordination flow.</p>
          </div>
          <span className="demo-simulated-label">Simulated data — no real request is created.</span>
        </div>
        <nav className="demo-progress" aria-label="Demo stages">
          {demoStages.map((item, index) => (
            <span className={index === stageIndex ? 'demo-stage demo-stage-current' : index < stageIndex ? 'demo-stage demo-stage-done' : 'demo-stage'} key={item}>
              <span>{index + 1}</span>{item}
            </span>
          ))}
        </nav>

        {stage === 'ASK' && (
          <div className="demo-content">
            <p className="section-kicker">THE REQUEST</p>
            <blockquote>“An elderly couple needs a prescription picked up.”</blockquote>
            <dl className="demo-facts">
              <div><dt>Category</dt><dd>Pharmacy</dd></div>
              <div><dt>Urgency</dt><dd>High</dd></div>
              <div><dt>People</dt><dd>2</dd></div>
              <div><dt>Location</dt><dd>Approximate area</dd></div>
              <div><dt>Need</dt><dd>Pharmacy pickup</dd></div>
            </dl>
            <p className="demo-explainer">Relay turns a neighbor’s description into clear details volunteers can act on. The location shown here is approximate.</p>
          </div>
        )}

        {stage === 'MATCH' && (
          <div className="demo-content">
            <p className="section-kicker">EXPLAINABLE MATCHES</p>
            <div className="demo-match-grid">
              <DemoVolunteer name="Nia Patel" score={96} distance="~1.2 km away" reasons={['Pharmacy pickup skill match', 'Available now', 'Closest suitable volunteer']} />
              <DemoVolunteer name="Dev Shah" score={84} distance="~2.8 km away" reasons={['Pharmacy pickup skill match', 'Available now', 'No active requests']} />
            </div>
            <p className="demo-explainer">Matches are ranked with transparent skill, availability, proximity, workload, and urgency factors.</p>
          </div>
        )}

        {stage === 'ACT' && (
          <div className="demo-content">
            <p className="section-kicker">HELP IN PROGRESS</p>
            <div className="demo-status-list">
              {[
                ['CLAIMED', 'Nia offers to help with the pickup.'],
                ['IN PROGRESS', 'Nia is on the way to the pharmacy.'],
                ['VOLUNTEER COMPLETED', 'Nia marks the pickup complete.'],
              ].map(([status, detail]) => <div className="demo-status-row" key={status}><span className="demo-status-dot">✓</span><div><strong>{status}</strong><span>{detail}</span></div></div>)}
            </div>
            <p className="demo-explainer">The volunteer updates progress so the requester can follow what is happening.</p>
          </div>
        )}

        {stage === 'RESOLVE' && (
          <div className="demo-content demo-resolved">
            <span className="demo-resolved-mark" aria-hidden="true">✓</span>
            <p className="section-kicker">TWO-SIDED COMPLETION</p>
            <h2>Help received and confirmed.</h2>
            <div className="demo-status-list">
              <div className="demo-status-row"><span className="demo-status-dot">✓</span><div><strong>REQUESTER CONFIRMED</strong><span>The couple confirms they received the prescription.</span></div></div>
              <div className="demo-status-row"><span className="demo-status-dot">✓</span><div><strong>RESOLVED</strong><span>The request is complete for both neighbors.</span></div></div>
            </div>
            <p className="demo-explainer">Relay coordinates everyday community assistance; it is not an emergency service.</p>
          </div>
        )}

        <footer className="demo-controls">
          <button className="text-button" type="button" onClick={onExit}>Back to Relay</button>
          <button className="submit-button" type="button" onClick={() => setStageIndex((index) => (index + 1) % demoStages.length)}>
            {stageIndex === demoStages.length - 1 ? 'Start again' : 'Continue'} <span aria-hidden="true">→</span>
          </button>
        </footer>
      </section>
    </main>
  );
}

function DemoVolunteer({ name, score, distance, reasons }: { name: string; score: number; distance: string; reasons: string[] }) {
  return (
    <article className="demo-volunteer-card">
      <div className="demo-volunteer-heading"><div><strong>{name}</strong><span>{distance}</span></div><span className="demo-score"><strong>{score}</strong><small>match</small></span></div>
      <span className="demo-availability">Available</span>
      <ul>{reasons.map((reason) => <li key={reason}><span aria-hidden="true">✓</span>{reason}</li>)}</ul>
    </article>
  );
}

function MatchesPanel({ request, loading, viewerId, onClaim, onReport, onBlock }: {
  request: RequestCardData;
  loading: boolean;
  viewerId: string;
  onClaim: (volunteerId: string) => void;
  onReport: (userId: string) => void;
  onBlock: (userId: string) => void;
}) {
  return (
    <section className="matches-panel" aria-labelledby="matches-title">
      <div className="matches-heading"><div><p className="section-kicker">NEARBY PEOPLE READY TO HELP</p><h3 id="matches-title">Top matches</h3></div><span className="match-sparkle">✳</span></div>
      {loading ? (
        <div className="match-loading" role="status"><span className="spinner" />Finding people who can help…</div>
      ) : request.matches?.length ? (
        <div className="match-list">
          {request.matches.slice(0, 2).map((match) => (
            <article className="match-card" key={match.volunteerId}>
              <div className="match-card-head">
                <div className="volunteer-avatar" aria-hidden="true">{match.name.slice(0, 1)}</div>
                <div className="match-person"><strong>{match.name}</strong><span>{match.distanceKm === null ? 'Distance unavailable' : `~${match.distanceKm.toFixed(1)} km away`}</span><span className={`availability-label availability-${match.availability.toLowerCase()}`}>{titleCase(match.availability)}</span></div>
                <div className="score-circle"><strong>{match.score}</strong><span>match</span></div>
              </div>
              <ul className="match-reasons">{match.reasons.map((reason) => <li key={reason}><span aria-hidden="true">✓</span>{humanizeReason(reason)}</li>)}</ul>
              <dl className="score-breakdown" aria-label="Match score factors">
                {Object.entries(match.scoreBreakdown).map(([factor, score]) => <div key={factor}><dt>{titleCase(factor)}</dt><dd>{score}</dd></div>)}
              </dl>
              {request.status === 'REQUESTED' && match.availability === 'AVAILABLE' && match.volunteerId === viewerId
                ? <button className="offer-button" type="button" onClick={() => onClaim(match.volunteerId)}>Help with this <span aria-hidden="true">→</span></button>
                : request.status === 'REQUESTED' && match.availability !== 'AVAILABLE'
                  ? <p className="claimed-note">This volunteer is {match.availability.toLowerCase()} and cannot claim this request.</p>
                  : request.status === 'REQUESTED'
                    ? <p className="claimed-note">This match can only be claimed by this volunteer after they sign in.</p>
                    : <p className="claimed-note">This request is already claimed.</p>}
              {match.volunteerId !== viewerId && <div className="match-safety-actions"><button type="button" className="text-button" onClick={() => onReport(match.volunteerId)}>Report</button><button type="button" className="text-button" onClick={() => onBlock(match.volunteerId)}>Block</button></div>}
            </article>
          ))}
        </div>
      ) : (
        <div className="no-matches"><span aria-hidden="true">⌁</span><strong>No available matches yet</strong><span>Your request stays on the community board.</span></div>
      )}
    </section>
  );
}

function RequestCard({ request, volunteer, viewerId, localDemo, finding, selected, onFindMatches, onClaim, onStatus, onConfirmReceived, onReport, onBlock, onReportUser }: {
  request: RequestCardData;
  volunteer?: Volunteer;
  viewerId: string;
  localDemo: boolean;
  finding: boolean;
  selected: boolean;
  onFindMatches: () => void;
  onClaim: (volunteerId: string) => void;
  onStatus: (status: RequestStatus) => void;
  onConfirmReceived: () => void;
  onReport: () => void;
  onBlock: (userId: string) => void;
  onReportUser: (userId: string) => void;
}) {
  const claimedByYou = request.isClaimedByYou || (localDemo && request.claimedBy && request.claimedBy === volunteer?.id);
  const statusAction = request.status === 'CLAIMED' && claimedByYou
    ? { label: 'Start helping', status: 'IN_PROGRESS' as const }
    : request.status === 'IN_PROGRESS' && claimedByYou
      ? { label: 'Mark help completed', status: 'VOLUNTEER_COMPLETED' as const }
      : undefined;
  const date = new Date(request.createdAt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

  return (
    <article className={`request-card ${selected ? 'request-card-selected' : ''}`}>
      <div className="request-card-top">
        <span className={`category-mark category-${request.category}`} aria-hidden="true">{categorySymbol(request.category)}</span>
        <div className="request-title-group"><div className="request-meta"><span>{titleCase(request.category)}</span>{request.urgency !== 'normal' && <span className={`urgency-label urgency-${request.urgency}`}>{request.urgency}</span>}</div><time dateTime={request.createdAt}>{date}</time></div>
        <StatusBadge status={request.status} />
      </div>
      <p className="request-description">{request.summary || request.description}</p>
      <div className="request-details"><span><span aria-hidden="true">⌖</span> {request.location.label}</span><span><span aria-hidden="true">♧</span> {request.peopleAffected} {request.peopleAffected === 1 ? 'person' : 'people'}</span></div>
      {request.mobilityNeeds && request.mobilityNeeds !== 'none' && request.mobilityNeeds !== 'unknown' && <p className="mobility-note">Mobility support: {titleCase(request.mobilityNeeds)}</p>}
      {request.status !== 'REQUESTED' && !claimedByYou && <p className="claimed-note">A neighbor has picked this up.</p>}
      {claimedByYou && <p className="claimed-you">CLAIMED BY YOU</p>}
      {(request.matches !== undefined || finding) && <MatchesPanel request={request} loading={finding} viewerId={viewerId} onClaim={onClaim} onReport={onReportUser} onBlock={(userId) => onBlock(userId)} />}
      <div className="request-actions">
        {request.status === 'REQUESTED' && <button className="quiet-action" type="button" onClick={onFindMatches} disabled={finding}>{finding ? 'Finding helpers…' : request.matches ? 'Refresh matches' : 'Find helpers'}</button>}
        {statusAction && <button className="help-button" type="button" onClick={() => onStatus(statusAction.status)}>{statusAction.label} <span aria-hidden="true">→</span></button>}
        {request.status === 'VOLUNTEER_COMPLETED' && request.isRequester && <button className="help-button" type="button" onClick={onConfirmReceived}>Confirm help received <span aria-hidden="true">→</span></button>}
        <button className="text-button" type="button" onClick={onReport}>Report request</button>
      </div>
    </article>
  );
}

function StatusBadge({ status }: { status: RequestStatus }) {
  const labels: Record<RequestStatus, string> = { REQUESTED: 'Requested', CLAIMED: 'Claimed', IN_PROGRESS: 'In progress', VOLUNTEER_COMPLETED: 'Help completed', REQUESTER_CONFIRMED: 'Confirmed', RESOLVED: 'Resolved' };
  return <span className={`status-badge status-${status.toLowerCase()}`}><i />{labels[status]}</span>;
}

function ProfileSetup({ onSave }: { onSave: (name: string, roles: CommunityProfile['roles']) => void }) {
  const [name, setName] = useState('');
  const [volunteer, setVolunteer] = useState(false);
  return (
    <form className="profile-setup" onSubmit={(event) => { event.preventDefault(); onSave(name.trim(), volunteer ? ['REQUESTER', 'VOLUNTEER'] : ['REQUESTER']); }}>
      <p className="section-kicker">YOUR COMMUNITY PROFILE</p>
      <h2>Welcome to Relay</h2>
      <p>Choose how you’d like to participate. You can ask for help and volunteer from the same account.</p>
      <label htmlFor="profile-name">Name shown to neighbors</label>
      <input id="profile-name" value={name} onChange={(event) => setName(event.target.value)} minLength={2} maxLength={80} required />
      <label className="check-row"><input type="checkbox" checked={volunteer} onChange={(event) => setVolunteer(event.target.checked)} /> I’d also like to volunteer</label>
      <button className="submit-button" type="submit">Save profile <span>→</span></button>
      <p className="privacy-note">Your account identity comes from Cognito. Email verification confirms account access, not a request’s truth.</p>
    </form>
  );
}

function VolunteerProfileEditor({ onError, onNotice }: { onError: (message: string) => void; onNotice: (message: string) => void }) {
  const [label, setLabel] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [skills, setSkills] = useState<string[]>(['general_help']);
  const [availability, setAvailability] = useState<Volunteer['availability']>('OFFLINE');
  const [saving, setSaving] = useState(false);
  const skillOptions = ['pharmacy_pickup', 'transport', 'mobility_assistance', 'food_delivery', 'water_delivery', 'general_help'];

  useEffect(() => {
    void relayApi.getVolunteerProfile().then((saved) => {
      setLabel(saved.location.label);
      setSkills(saved.skills);
      setAvailability(saved.availability);
    }).catch(() => undefined);
  }, []);

  function shareLocation() {
    if (!navigator.geolocation) {
      onError('This browser does not support location sharing. You can enter a neighborhood instead.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => { setLatitude(String(coords.latitude)); setLongitude(String(coords.longitude)); },
      () => onError('Location was not shared. A neighborhood label is enough to create your volunteer profile.'),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (Boolean(latitude) !== Boolean(longitude)) {
      onError('Share both coordinates, or leave both blank.');
      return;
    }
    setSaving(true);
    const location: Volunteer['location'] = { label: label.trim() || 'Location not shared' };
    if (latitude && longitude) {
      location.latitude = Number(latitude);
      location.longitude = Number(longitude);
    }
    try {
      await relayApi.saveVolunteerProfile({ location, skills, availability });
      onNotice('Volunteer profile saved. Your location is rounded before storage and hidden from other users.');
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Could not save volunteer profile.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <details className="volunteer-profile-editor">
      <summary>Volunteer profile and availability</summary>
      <form onSubmit={(event) => void save(event)}>
        <label htmlFor="volunteer-location">Neighborhood or landmark</label>
        <input id="volunteer-location" value={label} maxLength={120} onChange={(event) => setLabel(event.target.value)} placeholder="e.g. Block C" />
        <p className="field-hint">Only the neighborhood label is shown publicly. Exact coordinates are rounded for matching and never returned by the API.</p>
        <button type="button" className="quiet-action" onClick={shareLocation}>Use my approximate location</button>
        <div className="profile-skills">{skillOptions.map((skill) => <label className="check-row" key={skill}><input type="checkbox" checked={skills.includes(skill)} onChange={(event) => setSkills((current) => event.target.checked ? [...current, skill] : current.filter((item) => item !== skill))} />{formatSkill(skill)}</label>)}</div>
        <label htmlFor="availability">Availability</label>
        <select id="availability" value={availability} onChange={(event) => setAvailability(event.target.value as Volunteer['availability'])}>
          <option value="AVAILABLE">Available</option><option value="BUSY">Busy</option><option value="OFFLINE">Offline</option>
        </select>
        <button className="submit-button" disabled={saving}>{saving ? 'Saving…' : 'Save volunteer profile'}</button>
      </form>
    </details>
  );
}

function BlockSettings({ onNotice, onError }: { onNotice: (message: string) => void; onError: (message: string) => void }) {
  const [blocked, setBlocked] = useState<string[]>([]);
  useEffect(() => {
    const refresh = () => { void relayApi.listBlocks().then(setBlocked).catch(() => undefined); };
    refresh();
    window.addEventListener('relay-blocks-updated', refresh);
    return () => window.removeEventListener('relay-blocks-updated', refresh);
  }, []);
  async function unblock(userId: string) {
    try {
      await relayApi.unblockUser(userId);
      setBlocked((current) => current.filter((id) => id !== userId));
      onNotice('The account is unblocked. It may appear in future matches.');
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Could not unblock this account.');
    }
  }
  return (
    <details className="blocked-settings">
      <summary>Blocked accounts ({blocked.length})</summary>
      {blocked.length ? blocked.map((id) => <div className="blocked-user" key={id}><span>Account {id.slice(0, 8)}…</span><button className="text-button" type="button" onClick={() => void unblock(id)}>Unblock</button></div>) : <p className="field-hint">You have not blocked any accounts.</p>}
    </details>
  );
}

function titleCase(value: string) {
  return value.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatSkill(value: string) {
  return titleCase(value.replace(/_delivery$/, ' delivery').replace(/_pickup$/, ' pickup'));
}

function categorySymbol(category: RequestCategory) {
  if (category === 'transport') return '↗';
  if (category === 'food' || category === 'water') return '✳';
  if (category === 'pharmacy') return '＋';
  return '⌁';
}

function humanizeReason(reason: string) {
  return reason.replace('Has the required ', '').replace(' skill', ' skill match');
}

function looksLikeEmergency(description: string): boolean {
  return /can't breathe|cannot breathe|difficulty breathing|unconscious|not waking|severe bleeding|heart attack|stroke|overdose|suicid|immediate danger|being attacked|fire in/i.test(description);
}

export default App;
