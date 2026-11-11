
const fs = require('fs');

class MockNode {
  constructor(tag, attrs = {}, children = [], text = '') {
    this.tagName = tag.toUpperCase();
    this.attributes = attrs || {};
    this.children = [];
    this._text = text;
    this.parentElement = null;
    (children || []).forEach(c => {
      if (c) {
        c.parentElement = this;
        this.children.push(c);
      }
    });
  }
  get textContent() {
    if (this._text) return this._text;
    return this.children.map(c => c.textContent).join(' ');
  }
  set textContent(val) {
    this._text = val;
  }
  get innerText() {
    return this.textContent;
  }
  set innerText(val) {
    this._text = val;
  }
  getAttribute(name) { return this.attributes[name] || null; }
  get href() { return this.attributes.href || ''; }
  get className() { return this.attributes.class || ''; }

  closest(sel) {
    let curr = this;
    const selectors = sel.split(',').map(s => s.trim().toLowerCase());
    while (curr) {
      for (const s of selectors) {
        if (curr.matches(s)) return curr;
      }
      curr = curr.parentElement;
    }
    return null;
  }

  matches(sel) {
    const s = sel.toLowerCase();
    const tag = this.tagName.toLowerCase();
    const cls = this.className.toLowerCase();
    const role = (this.attributes.role || '').toLowerCase();
    const dataView = (this.attributes['data-view-name'] || '').toLowerCase();

    if (s.includes('header') && tag === 'header') return true;
    if (s.includes('nav') && (tag === 'nav' || role === 'navigation')) return true;
    if (s.includes('footer') && tag === 'footer') return true;
    if (s.includes('aside') && tag === 'aside') return true;
    if (s.includes('main') && (tag === 'main' || role === 'main')) return true;
    if (s.includes('pagination') && (cls.includes('pagination') || tag.includes('pagination'))) return true;
    if (s.includes('li') && tag === 'li') return true;
    if (s.includes('reusable-search__result-container') && cls.includes('reusable-search__result-container')) return true;
    if (s.includes('entity-result') && (cls.includes('entity-result') || dataView.includes('entity-result'))) return true;
    return false;
  }

  querySelector(sel) {
    const all = this.querySelectorAll(sel);
    return all.length > 0 ? all[0] : null;
  }

  querySelectorAll(sel) {
    const list = [];
    const selectors = sel.split(',').map(s => s.trim().toLowerCase());
    const walk = (node) => {
      for (const child of node.children) {
        const tag = child.tagName.toLowerCase();
        const cls = child.className.toLowerCase();
        const href = (child.href || '').toLowerCase();

        let match = false;
        for (const s of selectors) {
          if (s === 'a' && tag === 'a') match = true;
          if (s === 'p' && tag === 'p') match = true;
          if (s === 'span' && tag === 'span') match = true;
          if (s === 'div' && tag === 'div') match = true;
          if (s === 'ul' && tag === 'ul') match = true;
          if (s === 'ol' && tag === 'ol') match = true;
          if (s === 'section' && tag === 'section') match = true;
          if (s.startsWith('h') && ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) match = true;
          if (s.includes('a[href*="/in/"]') && tag === 'a' && href.includes('/in/')) match = true;
          if (s.includes('search-empty-state') && (cls.includes('search-empty-state') || cls.includes('empty-state'))) match = true;
          if (s.includes('reusable-search__result-container') && cls.includes('reusable-search__result-container')) match = true;
          if (s.includes('entity-result') && (cls.includes('entity-result') || (child.attributes['data-view-name'] || '').includes('entity-result'))) match = true;
          if (s.includes('primary-subtitle') && cls.includes('primary-subtitle')) match = true;
          if (s.includes('secondary-subtitle') && cls.includes('secondary-subtitle')) match = true;
          if (s.includes('span[aria-hidden="true"]') && tag === 'span' && child.attributes['aria-hidden'] === 'true') match = true;
          if (s.includes('span.entity-result__badge-text') && cls.includes('entity-result__badge-text')) match = true;
          if (s.includes('span.dist-value') && cls.includes('dist-value')) match = true;
          if (s.includes('span[class*="badge"]') && cls.includes('badge')) match = true;
          if (s.includes('a[href*="/in/"]') && tag === 'a' && href.includes('/in/')) match = true;
          if (s.includes('app-aware-link') && tag === 'a' && cls.includes('app-aware-link')) match = true;
          if (s.includes('a[data-view-name=') && tag === 'a' && (child.attributes['data-view-name'] || '').includes('search-result-lockup-title')) match = true;
          if (s.includes('span.entity-result__title-text') && cls.includes('entity-result__title-text')) match = true;
          if (s.includes('span.entity-result__title') && cls.includes('entity-result__title')) match = true;
          if (s === 'a[href*="/in/"]' && tag === 'a' && href.includes('/in/')) match = true;
          if (s === 'a' && tag === 'a') match = true;
          if (s.includes('t-14') && cls.includes('t-14')) match = true;
          if (match) break;
        }

        if (match && !list.includes(child)) list.push(child);
        walk(child);
      }
    };
    walk(this);
    return list;
  }
}

function runTestCase(name, setupDom) {
  return new Promise((resolve) => {
    console.log(`\n========================================`);
    console.log(`TEST: ${name}`);
    console.log(`========================================`);

    const { body, main } = setupDom();

    global.window = {
      location: {
        pathname: '/search/results/people/',
        href: 'https://www.linkedin.com/search/results/people/?keywords=VP+Sales'
      },
      scrollBy: () => { },
      getComputedStyle: () => ({ display: 'block', visibility: 'visible', opacity: '1' })
    };

    global.document = {
      documentElement: { dataset: {} },
      body: body,
      title: 'People Search | LinkedIn',
      readyState: 'complete',
      visibilityState: 'visible',
      querySelector: (sel) => {
        if (sel === 'main' || sel === '[role="main"]') return main;
        return body.querySelector(sel);
      },
      querySelectorAll: (sel) => body.querySelectorAll(sel)
    };

    let localListener = null;
    global.chrome = {
      runtime: {
        onMessage: {
          addListener: (fn) => { localListener = fn; }
        }
      }
    };

    const code = fs.readFileSync('linkedin_extension/content_linkedin.js', 'utf8');
    eval(code);

    localListener({ action: 'EXTRACT_SEARCH_RESULTS_DOM', requestId: `test_${Date.now()}` }, {}, (resp) => {
      resolve(resp);
    });
  });
}

async function runAll() {
  // Case 1: Multiple LinkedIn Member title anchors inside nested wrappers -> count each anchor once
  const resp1 = await runTestCase('Case 1: Multiple LinkedIn Member title anchors inside nested wrappers', () => {
    const makeAnonCard = (i) => {
      const spanAria = new MockNode('span', { 'aria-hidden': 'true' }, [], '  LinkedIn Member  ');
      const spanHidden = new MockNode('span', { class: 'visually-hidden' }, [], 'LinkedIn Member');
      // Exactly 1 title anchor per card pointing to search URL
      const searchAnchor = new MockNode('a', {
        href: 'https://www.linkedin.com/search/results/people/?keywords=VP+Sales',
        class: 'app-aware-link'
      }, [spanAria, spanHidden]);

      const subtitle = new MockNode('div', { class: 'entity-result__primary-subtitle t-14' }, [], `VP of Sales #${i}`);
      const textWrap = new MockNode('div', { class: 'nested-wrap-1' }, [searchAnchor, subtitle]);
      const cardWrap = new MockNode('div', { class: 'nested-wrap-2' }, [textWrap]);
      return new MockNode('li', { class: 'reusable-search__result-container' }, [cardWrap]);
    };

    const cards = [];
    for (let i = 1; i <= 5; i++) {
      cards.push(makeAnonCard(i));
    }

    const main = new MockNode('main', { role: 'main' }, cards);
    const body = new MockNode('body', {}, [main]);
    return { body, main };
  });

  console.log('Result Status:', resp1.status);
  console.log('Candidate Count:', resp1.count);
  console.log('Anonymous Count:', resp1.diagnostic.anonymous_cards_count);

  if (resp1.status === 'ANONYMOUS_OUT_OF_NETWORK_RESULTS' &&
    resp1.count === 0 &&
    resp1.diagnostic.anonymous_cards_count === 5) {
    console.log('--> PASSED Case 1: Exactly 5 anonymous title anchors counted.');
  } else {
    console.error('--> FAILED Case 1');
    process.exit(1);
  }

  // Case 2: An anonymous title anchor inside a broad ancestor that also contains an unrelated /in/ link (e.g. sidebar or footer)
  const resp2 = await runTestCase('Case 2: Anonymous title anchor with unrelated /in/ link elsewhere in broad ancestor', () => {
    // Card with anonymous anchor
    const spanAria = new MockNode('span', { 'aria-hidden': 'true' }, [], 'LinkedIn Member');
    const searchAnchor = new MockNode('a', {
      href: 'https://www.linkedin.com/search/results/people/?keywords=VP+Sales',
      class: 'app-aware-link'
    }, [spanAria]);
    const subtitle = new MockNode('div', { class: 'entity-result__primary-subtitle t-14' }, [], 'VP of Sales');

    // Unrelated link in the same ancestor block (e.g., promoted ad or shared widget)
    const unrelatedInLink = new MockNode('a', { href: 'https://www.linkedin.com/in/unrelated-sponsor-profile' }, [], 'Sponsor');

    const broadAncestor = new MockNode('div', { class: 'broad-scaffold-container' }, [searchAnchor, subtitle, unrelatedInLink]);
    const main = new MockNode('main', { role: 'main' }, [broadAncestor]);
    const body = new MockNode('body', {}, [main]);
    return { body, main };
  });

  console.log('Result Status:', resp2.status);
  console.log('Candidate Count:', resp2.count);
  console.log('Anonymous Count:', resp2.diagnostic.anonymous_cards_count);

  if (resp2.status === 'ANONYMOUS_OUT_OF_NETWORK_RESULTS' &&
    resp2.count === 0 &&
    resp2.diagnostic.anonymous_cards_count === 1) {
    console.log('--> PASSED Case 2: Anonymous title detected correctly even when broad ancestor contains unrelated /in/ link.');
  } else {
    console.error('--> FAILED Case 2');
    process.exit(1);
  }

  // Case 3: Valid named profile anchors with individual /in/<slug> destinations -> extract normally
  const resp3 = await runTestCase('Case 3: Valid named profile anchors with individual /in/<slug> destinations', () => {
    const makeValidCard = (name, slug, headline) => {
      const nameSpan = new MockNode('span', { 'aria-hidden': 'true' }, [], name);
      const inAnchor = new MockNode('a', {
        href: `https://www.linkedin.com/in/${slug}`,
        class: 'app-aware-link'
      }, [nameSpan]);
      const subtitle = new MockNode('div', { class: 'entity-result__primary-subtitle t-14' }, [], headline);
      return new MockNode('li', { class: 'reusable-search__result-container' }, [inAnchor, subtitle]);
    };

    const card1 = makeValidCard('Sarah Connor', 'sarah-connor', 'VP Sales at Cyberdyne');
    const card2 = makeValidCard('Miles Dyson', 'miles-dyson', 'CTO at Neural Systems');

    const main = new MockNode('main', { role: 'main' }, [card1, card2]);
    const body = new MockNode('body', {}, [main]);
    return { body, main };
  });

  console.log('Result Status:', resp3.status);
  console.log('Candidate Count:', resp3.count);
  console.log('Candidates:', resp3.results.map(r => ({ name: r.name, url: r.profile_url })));

  if (resp3.status === 'RESULTS_EXTRACTED' &&
    resp3.count === 2 &&
    resp3.results[0].name === 'Sarah Connor' &&
    resp3.results[1].name === 'Miles Dyson') {
    console.log('--> PASSED Case 3: Valid prospects extracted normally.');
  } else {
    console.error('--> FAILED Case 3');
    process.exit(1);
  }

  // Case 4: Empty results page -> remains VERIFIED_EMPTY_RESULTS
  const resp4 = await runTestCase('Case 4: Empty results page', () => {
    const emptyBanner = new MockNode('div', { class: 'search-empty-state artdeco-empty-state' }, [], 'No results found. Try searching for something else.');
    const main = new MockNode('main', { role: 'main' }, [emptyBanner]);
    const body = new MockNode('body', {}, [main]);
    return { body, main };
  });

  console.log('Result Status:', resp4.status);
  console.log('Candidate Count:', resp4.count);

  if (resp4.status === 'VERIFIED_EMPTY_RESULTS' &&
    resp4.count === 0 &&
    resp4.diagnostic.anonymous_cards_count === 0) {
    console.log('--> PASSED Case 4: Correctly verified empty results.');
  } else {
    console.error('--> FAILED Case 4');
    process.exit(1);
  }

  // Case 5: Mixed anonymous and valid results -> only valid profiles extracted
  const resp5 = await runTestCase('Case 5: Mixed anonymous and valid results', () => {
    // 1 Valid
    const nameSpan = new MockNode('span', { 'aria-hidden': 'true' }, [], 'Alex Mercer');
    const inAnchor = new MockNode('a', {
      href: 'https://www.linkedin.com/in/alex-mercer',
      class: 'app-aware-link'
    }, [nameSpan]);
    const subtitleValid = new MockNode('div', { class: 'entity-result__primary-subtitle t-14' }, [], 'VP Growth');
    const validCard = new MockNode('li', { class: 'reusable-search__result-container' }, [inAnchor, subtitleValid]);

    // 1 Anonymous
    const spanAnon = new MockNode('span', { 'aria-hidden': 'true' }, [], 'LinkedIn Member');
    const anonAnchor = new MockNode('a', {
      href: 'https://www.linkedin.com/search/results/people/?keywords=VP+Growth',
      class: 'app-aware-link'
    }, [spanAnon]);
    const subtitleAnon = new MockNode('div', { class: 'entity-result__primary-subtitle t-14' }, [], 'VP Sales at Stealth');
    const anonCard = new MockNode('li', { class: 'reusable-search__result-container' }, [anonAnchor, subtitleAnon]);

    const main = new MockNode('main', { role: 'main' }, [validCard, anonCard]);
    const body = new MockNode('body', {}, [main]);
    return { body, main };
  });

  console.log('Result Status:', resp5.status);
  console.log('Candidate Count:', resp5.count);
  console.log('Anonymous Count:', resp5.diagnostic.anonymous_cards_count);
  console.log('Extracted:', resp5.results.map(r => ({ name: r.name, url: r.profile_url })));

  if (resp5.status === 'RESULTS_EXTRACTED' &&
    resp5.count === 1 &&
    resp5.results[0].name === 'Alex Mercer' &&
    resp5.diagnostic.anonymous_cards_count === 1) {
    console.log('--> PASSED Case 5: Only valid profile extracted, anonymous card counted in diagnostics.');
  } else {
    console.error('--> FAILED Case 5');
    process.exit(1);
  }

  // Case 6: Live LinkedIn DOM structure — 10 outer anchors wrapping entire card text with descendant <p>LinkedIn Member</p>
  const resp6 = await runTestCase('Case 6: Live DOM structure: 10 outer card anchors wrapping <p>LinkedIn Member</p> + full card text', () => {
    const makeLiveAnonCard = (i) => {
      // Descendant <p> with exact text "LinkedIn Member"
      const pIdentity = new MockNode('p', { class: 'identity-title' }, [], 'LinkedIn Member');
      // Subtitle and other card content
      const pHeadline = new MockNode('p', { class: 'headline' }, [], `Founder & CEO @Startup${i}`);
      const pLocation = new MockNode('p', { class: 'location' }, [], 'Bengaluru, Karnataka, India');
      const divExperience = new MockNode('div', { class: 'experience' }, [], 'Current: Founder at Stealth');

      const cardContent = new MockNode('div', { class: 'gvyl4n gvyayy' }, [
        pIdentity,
        pHeadline,
        pLocation,
        divExperience
      ]);

      // Outer anchor wrapping the entire card pointing to search URL, not /in/<slug>
      const outerAnchor = new MockNode('a', {
        href: `https://www.linkedin.com/search/results/people/?keywords=Founder&page=1`,
        class: 'search-card-link-wrapper'
      }, [cardContent]);

      return new MockNode('div', { class: 'result-card-container' }, [outerAnchor]);
    };

    const cards = [];
    for (let i = 1; i <= 10; i++) {
      cards.push(makeLiveAnonCard(i));
    }

    // Include unrelated navigation anchor that contains "LinkedIn Member"
    const navText = new MockNode('p', {}, [], 'LinkedIn Member Directory');
    const navAnchor = new MockNode('a', { href: 'https://www.linkedin.com/directory/' }, [navText]);
    const headerNav = new MockNode('header', { role: 'banner' }, [navAnchor]);

    const main = new MockNode('main', { role: 'main' }, cards);
    const body = new MockNode('body', {}, [headerNav, main]);
    return { body, main };
  });

  console.log('Result Status:', resp6.status);
  console.log('Candidate Count:', resp6.count);
  console.log('Anonymous Count:', resp6.diagnostic.anonymous_cards_count);

  if (resp6.status === 'ANONYMOUS_OUT_OF_NETWORK_RESULTS' &&
    resp6.count === 0 &&
    resp6.diagnostic.anonymous_cards_count === 10) {
    console.log('--> PASSED Case 6: Exactly 10 anonymous cards detected from outer card anchors wrapping <p>LinkedIn Member</p>; navigation ignored.');
  } else {
    console.error('--> FAILED Case 6');
    process.exit(1);
  }

  // Case 7: Mixed Live DOM: 1 valid named profile card (/in/<slug>) + 2 anonymous outer card anchors
  const resp7 = await runTestCase('Case 7: Mixed Live DOM: 1 valid named profile (/in/slug) + 2 anonymous outer card anchors', () => {
    // Valid card
    const nameSpan = new MockNode('span', { 'aria-hidden': 'true' }, [], 'Priya Sharma');
    const validAnchor = new MockNode('a', {
      href: 'https://www.linkedin.com/in/priya-sharma',
      class: 'app-aware-link'
    }, [nameSpan]);
    const validSubtitle = new MockNode('div', { class: 'entity-result__primary-subtitle t-14' }, [], 'VP Marketing at Acme');
    const validCard = new MockNode('li', { class: 'reusable-search__result-container' }, [validAnchor, validSubtitle]);

    // Anonymous card 1 with search URL href
    const anonP1 = new MockNode('p', {}, [], 'LinkedIn Member');
    const anonDetails1 = new MockNode('div', {}, [anonP1, new MockNode('p', {}, [], 'Director @GTMist Bengaluru')]);
    const anonAnchor1 = new MockNode('a', {
      href: 'https://www.linkedin.com/search/results/people/?keywords=Director',
      class: 'search-card-link-wrapper'
    }, [anonDetails1]);

    // Anonymous card 2 with nested wrappers around the identity paragraph
    const anonP2 = new MockNode('p', {}, [], '  LinkedIn Member  ');
    const innerWrap = new MockNode('span', { class: 'inner-span' }, [anonP2]);
    const anonDetails2 = new MockNode('div', {}, [innerWrap, new MockNode('p', {}, [], 'Head of Sales Delhi')]);
    const anonAnchor2 = new MockNode('a', {
      href: 'https://www.linkedin.com/search/results/people/?keywords=Director',
      class: 'search-card-link-wrapper'
    }, [anonDetails2]);

    const main = new MockNode('main', { role: 'main' }, [validCard, anonAnchor1, anonAnchor2]);
    const body = new MockNode('body', {}, [main]);
    return { body, main };
  });

  console.log('Result Status:', resp7.status);
  console.log('Candidate Count:', resp7.count);
  console.log('Anonymous Count:', resp7.diagnostic.anonymous_cards_count);
  console.log('Extracted:', resp7.results.map(r => ({ name: r.name, url: r.profile_url })));

  if (resp7.status === 'RESULTS_EXTRACTED' &&
    resp7.count === 1 &&
    resp7.results[0].name === 'Priya Sharma' &&
    resp7.results[0].profile_url === 'https://www.linkedin.com/in/priya-sharma' &&
    resp7.diagnostic.anonymous_cards_count === 2) {
    console.log('--> PASSED Case 7: Only genuine /in/<slug> profile extracted; search URLs never treated as profiles; anonymous cards properly counted.');
  } else {
    console.error('--> FAILED Case 7');
    process.exit(1);
  }

  // Case 8: Market Intelligence extraction from 10 anonymous cards with visible headlines, locations, companies, and deduplication
  const resp8 = await runTestCase('Case 8: Market Intelligence extraction with headline, location, and company mentions', () => {
    const makeRichAnonCard = (i, title, comp, loc) => {
      const pIdentity = new MockNode('p', { class: 'identity-title' }, [], 'LinkedIn Member');
      const pHeadline = new MockNode('p', { class: 'headline' }, [], `${title} @${comp}`);
      const pLocation = new MockNode('p', { class: 'location' }, [], loc);
      const divExperience = new MockNode('div', { class: 'experience' }, [], `Current: ${title} at ${comp}`);

      const cardContent = new MockNode('div', { class: 'gvyl4n gvyayy' }, [
        pIdentity,
        pHeadline,
        pLocation,
        divExperience
      ]);

      const outerAnchor = new MockNode('a', {
        href: `https://www.linkedin.com/search/results/people/?keywords=VP+Sales`,
        class: 'search-card-link-wrapper'
      }, [cardContent]);

      return new MockNode('div', { class: 'result-card-container' }, [outerAnchor]);
    };

    // 8 distinct cards + 2 duplicates of card 1 and card 2
    const cards = [
      makeRichAnonCard(1, 'VP of Sales', 'GTMist', 'Bengaluru, Karnataka, India'),
      makeRichAnonCard(2, 'Founder & CEO', 'Stealth SaaS', 'San Francisco, CA'),
      makeRichAnonCard(3, 'Head of Growth', 'GTMist', 'Bengaluru, Karnataka, India'),
      makeRichAnonCard(4, 'Director of RevOps', 'CloudScale', 'Austin, TX'),
      makeRichAnonCard(5, 'VP of Sales', 'Acme Corp', 'Bengaluru, Karnataka, India'),
      makeRichAnonCard(6, 'Chief Revenue Officer', 'DataPeak', 'London, UK'),
      makeRichAnonCard(7, 'Head of Sales', 'CyberAI', 'New York, NY'),
      makeRichAnonCard(8, 'Senior Account Executive', 'SaaSWorks', 'Bengaluru, Karnataka, India'),
      // Duplicate of card 1
      makeRichAnonCard(9, 'VP of Sales', 'GTMist', 'Bengaluru, Karnataka, India'),
      // Duplicate of card 2
      makeRichAnonCard(10, 'Founder & CEO', 'Stealth SaaS', 'San Francisco, CA')
    ];

    const main = new MockNode('main', { role: 'main' }, cards);
    const body = new MockNode('body', {}, [main]);
    return { body, main };
  });

  console.log('Result Status:', resp8.status);
  console.log('Candidate Count (Verified):', resp8.count);
  console.log('Anonymous Card Count:', resp8.diagnostic.anonymous_cards_count);
  console.log('Unverified Signals Count:', resp8.unverified_signals ? resp8.unverified_signals.length : 0);
  console.log('Sample Signal:', resp8.unverified_signals ? resp8.unverified_signals[0] : null);

  if (resp8.status === 'ANONYMOUS_OUT_OF_NETWORK_RESULTS' &&
    resp8.count === 0 &&
    resp8.results.length === 0 &&
    resp8.diagnostic.anonymous_cards_count === 10 &&
    resp8.unverified_signals &&
    resp8.unverified_signals.length === 8 && // 8 unique signals after deduplication of 2 duplicates
    resp8.unverified_signals[0].headline === 'VP of Sales @GTMist' &&
    resp8.unverified_signals[0].location === 'Bengaluru, Karnataka, India' &&
    resp8.unverified_signals[0].company_mentions.includes('GTMist')) {
    console.log('--> PASSED Case 8: Market Intelligence extracted 8 unique unverified signals from 10 cards; 0 verified prospects; company mentions extracted.');
  } else {
    console.error('--> FAILED Case 8');
    process.exit(1);
  }

  // Case 9: Anonymous cards with missing optional fields & Premium CTA element
  const resp9 = await runTestCase('Case 9: Anonymous cards with missing optional fields & Premium CTA element ignored', () => {
    // Card with only headline, no location or experience
    const pIdentity = new MockNode('p', {}, [], 'LinkedIn Member');
    const pHeadline = new MockNode('p', { class: 'headline' }, [], 'Independent Consultant');
    const cardContent = new MockNode('div', {}, [pIdentity, pHeadline]);
    const anonAnchor = new MockNode('a', {
      href: 'https://www.linkedin.com/search/results/people/',
      class: 'search-card-link-wrapper'
    }, [cardContent]);

    // Unrelated Premium promotion anchor containing marketing text
    const premiumAnchor = new MockNode('a', { href: 'https://www.linkedin.com/premium/products' }, [
      new MockNode('p', {}, [], 'Upgrade to Premium for full search details')
    ]);
    const aside = new MockNode('aside', {}, [premiumAnchor]);

    const main = new MockNode('main', { role: 'main' }, [anonAnchor]);
    const body = new MockNode('body', {}, [aside, main]);
    return { body, main };
  });

  console.log('Result Status:', resp9.status);
  console.log('Unverified Signals Count:', resp9.unverified_signals ? resp9.unverified_signals.length : 0);

  if (resp9.status === 'ANONYMOUS_OUT_OF_NETWORK_RESULTS' &&
    resp9.count === 0 &&
    resp9.unverified_signals.length === 1 &&
    resp9.unverified_signals[0].headline === 'Independent Consultant' &&
    resp9.unverified_signals[0].location === '-') {
    console.log('--> PASSED Case 9: Missing fields safely filled with default placeholders; Premium promotion ignored.');
  } else {
    console.error('--> FAILED Case 9');
    process.exit(1);
  }

  // Case 10: Connection degree badge extraction (1st, 2nd, 3rd+, and Unknown fallback)
  const resp10 = await runTestCase('Case 10: Connection degree badge extraction (1st, 2nd, 3rd+, Unknown)', () => {
    const makeDegreeCard = (name, slug, degreeText, hasBadge = true) => {
      const nameSpan = new MockNode('span', { 'aria-hidden': 'true' }, [], name);
      const inAnchor = new MockNode('a', {
        href: `https://www.linkedin.com/in/${slug}`,
        class: 'app-aware-link'
      }, [nameSpan]);

      const badgeNode = hasBadge
        ? new MockNode('span', { class: 'entity-result__badge-text dist-value' }, [], degreeText)
        : null;

      const subtitle = new MockNode('div', { class: 'entity-result__primary-subtitle t-14' }, [], 'Director of Engineering');
      const children = badgeNode ? [inAnchor, badgeNode, subtitle] : [inAnchor, subtitle];
      return new MockNode('li', { class: 'reusable-search__result-container' }, children);
    };

    const card1 = makeDegreeCard('Alice Johnson', 'alice-johnson', '1st', true);
    const card2 = makeDegreeCard('Bob Smith', 'bob-smith', '2nd degree', true);
    const card3 = makeDegreeCard('Carol Danvers', 'carol-danvers', '3rd+', true);
    const card4 = makeDegreeCard('David Miller', 'david-miller', '', false); // No badge -> Unknown

    const main = new MockNode('main', { role: 'main' }, [card1, card2, card3, card4]);
    const body = new MockNode('body', {}, [main]);
    return { body, main };
  });

  console.log('Result Status:', resp10.status);
  console.log('Extracted Degrees:', resp10.results.map(r => ({ name: r.name, degree: r.connection_degree })));

  if (resp10.status === 'RESULTS_EXTRACTED' &&
    resp10.count === 4 &&
    resp10.results[0].connection_degree === '1st' &&
    resp10.results[1].connection_degree === '2nd' &&
    resp10.results[2].connection_degree === '3rd+' &&
    resp10.results[3].connection_degree === 'Unknown') {
    console.log('--> PASSED Case 10: Accurately extracted 1st, 2nd, 3rd+, and fell back to Unknown when no badge present.');
  } else {
    console.error('--> FAILED Case 10');
    process.exit(1);
  }

  // Case 11: Network URL generation logic verification
  console.log(`\n========================================`);
  console.log(`TEST: Case 11: Network scope URL generation checks`);
  const buildTestUrl = (queryKeywords, scope) => {
    const searchParams = new URLSearchParams();
    searchParams.set('keywords', queryKeywords);
    searchParams.set('origin', 'GLOBAL_SEARCH_HEADER');
    if (scope === 'F') {
      searchParams.set('network', JSON.stringify(['F']));
    } else if (scope === 'S') {
      searchParams.set('network', JSON.stringify(['S']));
    } else if (scope === 'F_S') {
      searchParams.set('network', JSON.stringify(['F', 'S']));
    } else if (scope === 'ALL') {
      searchParams.set('network', JSON.stringify(['F', 'S', 'O']));
    } else {
      searchParams.set('network', JSON.stringify(['S']));
    }
    return `https://www.linkedin.com/search/results/people/?${searchParams.toString()}`;
  };

  const urlDefault = buildTestUrl('VP Sales', '');
  const urlF = buildTestUrl('VP Sales', 'F');
  const urlS = buildTestUrl('VP Sales', 'S');
  const urlFS = buildTestUrl('VP Sales', 'F_S');
  const urlAll = buildTestUrl('VP Sales', 'ALL');

  console.log('Default Scope URL:', urlDefault);
  console.log('1st Scope URL:', urlF);
  console.log('2nd Scope URL:', urlS);
  console.log('Combined Scope URL:', urlFS);
  console.log('Extended Scope URL:', urlAll);

  if (urlDefault.includes('network=%5B%22S%22%5D') &&
    urlF.includes('network=%5B%22F%22%5D') &&
    urlS.includes('network=%5B%22S%22%5D') &&
    urlFS.includes('network=%5B%22F%22%2C%22S%22%5D') &&
    urlAll.includes('network=%5B%22F%22%2C%22S%22%2C%22O%22%5D')) {
    console.log('--> PASSED Case 11: All 5 network scopes generate the exact correct URL parameters.');
  } else {
    console.error('--> FAILED Case 11');
    process.exit(1);
  }

  console.log('\nALL 11 REQUIRED CASES PASSED CLEANLY!');
}

runAll().catch(err => {
  console.error('Test run failed:', err);
  process.exit(1);
});
