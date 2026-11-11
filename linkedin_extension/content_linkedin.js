// Content script running on LinkedIn tabs (https://*.linkedin.com/*)
// 1. Verifies whether LinkedIn DOM indicates an active authenticated session without reading cookies.
// 2. Extracts visible own-profile DOM data upon explicit user request from FameWeb.
// Strictly enforces zero transmission of cookies, session tokens, or authentication headers.

(function() {
  const EXTENSION_CONTENT_VERSION = "1.0.3";

  // If a previous version of the content script was injected into this document,
  // remove its message listener to prevent duplicate message responses.
  if (window.__famewebLinkedInMessageListener) {
    try {
      chrome.runtime.onMessage.removeListener(window.__famewebLinkedInMessageListener);
      console.log(`[LinkedIn Content] Removed previous message listener (was v${window.__famewebLinkedInContentInjected})`);
    } catch (e) {}
  }

  window.__famewebLinkedInContentInjected = EXTENSION_CONTENT_VERSION;
  console.log(`[LinkedIn Content] content_linkedin.js v${EXTENSION_CONTENT_VERSION} active on ${window.location.pathname}`);

  function checkDomAuthState() {
    // Check common authenticated elements on LinkedIn desktop:
    // e.g. global nav search, profile photo / me menu, feed nav
    const hasNav = !!document.querySelector('.global-nav, .feed-shared-update-v2, nav[aria-label="Primary Navigation"], #global-nav');
    const hasMeDropdown = !!document.querySelector('.global-nav__me, img[alt*="photo"], .feed-identity-module');
    const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');

    return hasNav || hasMeDropdown || !isLoginPage;
  }

  function cleanText(text) {
    if (!text) return "";
    return text.replace(/\s+/g, " ").trim();
  }

  // Determine if current page is likely the user's own profile or a profile page
  function inspectProfilePage() {
    const path = window.location.pathname;
    const isProfileUrl = path.startsWith('/in/') || path.startsWith('/in');
    
    // Check for self-profile edit indicators (buttons like "Edit public profile & URL", "Add profile section", edit pencil icons, or presence of /in/me)
    const hasEditProfileButton = !!document.querySelector('button[aria-label*="Edit"], a[href*="public-profile-settings"], button[aria-label*="Add profile section"], .pv-top-card__edit-photo, .profile-action-compose-button');
    const hasMeMenuMatch = path.includes('/in/me');
    
    // Get candidate vanity name from URL
    const urlParts = path.split('/').filter(Boolean);
    const vanityName = urlParts.length >= 2 ? urlParts[1] : '';

    return {
      isProfileUrl,
      isSelfProfileLikely: hasEditProfileButton || hasMeMenuMatch,
      vanityName,
      currentUrl: window.location.href.split('?')[0]
    };
  }

  // Discover user's own profile URL from navigation or profile widgets
  function discoverOwnProfileUrl() {
    // Strategy A: If already on a self profile page
    const pageCheck = inspectProfilePage();
    if (pageCheck.isProfileUrl && pageCheck.isSelfProfileLikely) {
      return { found: true, url: window.location.href.split('?')[0], method: 'current_self_profile' };
    }

    // Strategy B: Inspect global navigation "Me" / identity dropdown links
    // LinkedIn renders anchors to /in/<vanity> in .global-nav__me or profile link inside dropdown
    const navMeSelectors = [
      'a[href*="/in/"][data-control-name="identity_welcome_message"]',
      '.global-nav__me-content a[href*="/in/"]',
      'a.ember-view[href*="/in/"][href*="profile"]',
      '.feed-identity-module a[href*="/in/"]',
      'a.feed-identity-module__actor-link',
      'a[href*="/in/"][aria-label*="profile" i]',
      'a[href*="/in/"][class*="identity"]',
      '.global-nav__me a[href*="/in/"]'
    ];

    for (const sel of navMeSelectors) {
      const el = document.querySelector(sel);
      if (el && el.href && el.href.includes('/in/')) {
        const cleanHref = el.href.split('?')[0].replace(/\/+$/, '');
        // Ensure not generic /in/ or /in/me
        if (cleanHref.split('/in/')[1]) {
          return { found: true, url: cleanHref, method: 'nav_me_link' };
        }
      }
    }

    // Strategy C: Left rail identity card on feed (/feed/)
    const feedIdentityLinks = document.querySelectorAll('.feed-identity-module a, .identity-headline a');
    for (const link of feedIdentityLinks) {
      if (link.href && link.href.includes('/in/')) {
        const cleanHref = link.href.split('?')[0].replace(/\/+$/, '');
        if (cleanHref.split('/in/')[1]) {
          return { found: true, url: cleanHref, method: 'feed_identity_card' };
        }
      }
    }

    // Strategy D: Check any anchor in header containing /in/ (excluding company or search)
    const allInLinks = Array.from(document.querySelectorAll('header a[href*="/in/"], nav a[href*="/in/"]'));
    for (const link of allInLinks) {
      if (link.href && link.href.includes('/in/')) {
        const cleanHref = link.href.split('?')[0].replace(/\/+$/, '');
        const handle = cleanHref.split('/in/')[1];
        if (handle && !['feed', 'mynetwork', 'jobs', 'messaging', 'notifications'].includes(handle.toLowerCase())) {
          return { found: true, url: cleanHref, method: 'nav_header_link' };
        }
      }
    }

    // Strategy E: Safe LinkedIn self-profile redirect route
    // Navigating to https://www.linkedin.com/in/me/ natively redirects logged-in user to their own profile
    return { found: true, url: 'https://www.linkedin.com/in/me/', method: 'linkedin_me_redirect' };
  }

  // Progressively scroll down to trigger LinkedIn's lazy-loading observers for deeper sections
  async function autoScrollAndLoadSections() {
    const startTime = Date.now();
    console.log("[LinkedIn Extraction] AUTO_SCROLL_STARTED (+0ms)");

    const maxDurationMs = 3800; // Strict hard deadline to avoid exceeding background timeout
    const deadline = startTime + maxDurationMs;
    const maxSteps = 5; // Fixed small number of steps
    const stepSize = 650; // Scroll increment
    let currentStep = 0;

    try {
      while (currentStep < maxSteps && Date.now() < deadline) {
        currentStep++;
        const targetY = currentStep * stepSize;
        window.scrollTo({ top: targetY, behavior: 'instant' });

        const elapsed = Date.now() - startTime;
        console.log(`[LinkedIn Extraction] Scroll step ${currentStep}/${maxSteps} to ${targetY}px (+${elapsed}ms)`);

        // Brief delay for LinkedIn lazy-load observers to fire
        await new Promise(r => setTimeout(r, 180));

        // Check visibility of specific core sections
        const expEl = document.querySelector('#experience, section[id*="experience" i]');
        const eduEl = document.querySelector('#education, section[id*="education" i]');
        const skillsEl = document.querySelector('#skills, section[id*="skills" i]');

        if (expEl) {
          console.log(`[LinkedIn Extraction] EXPERIENCE_SECTION_IN_VIEW (+${Date.now() - startTime}ms)`);
        }
        if (eduEl) {
          console.log(`[LinkedIn Extraction] EDUCATION_SECTION_IN_VIEW (+${Date.now() - startTime}ms)`);
        }
        if (skillsEl) {
          console.log(`[LinkedIn Extraction] SKILLS_SECTION_IN_VIEW (+${Date.now() - startTime}ms)`);
        }

        // Early break if critical lower sections have rendered
        if ((expEl && eduEl && skillsEl) || (expEl && currentStep >= 4)) {
          console.log(`[LinkedIn Extraction] Core sections detected early at step ${currentStep} (+${Date.now() - startTime}ms)`);
          break;
        }
      }
    } finally {
      // Always restore scroll position to top even on error or timeout
      window.scrollTo({ top: 0, behavior: 'instant' });
      const totalElapsed = Date.now() - startTime;
      console.log(`[LinkedIn Extraction] AUTO_SCROLL_COMPLETED (+${totalElapsed}ms)`);
    }
  }

  // Helper: Expand inline 'see more' buttons inside a section or container
  function expandSeeMoreButtons(container, sectionName = "") {
    if (!container) return;
    try {
      const seeMoreBtns = container.querySelectorAll(
        'button.inline-show-more-text__button, ' +
        'button[aria-label*="see more" i], ' +
        '.pv-profile-section__see-more-inline, ' +
        'button[aria-label*="Show more" i]'
      );
      let clickCount = 0;
      seeMoreBtns.forEach(btn => {
        if (typeof btn.click === 'function') {
          btn.click();
          clickCount++;
        }
      });
      if (clickCount > 0) {
        console.log(`[LinkedIn Extraction] SECTION_EXPANSION: ${sectionName || 'section'} (${clickCount} buttons clicked)`);
      }
    } catch (e) {}
  }

  // Robust, multi-strategy DOM extraction for visible profile sections
  function extractProfileFromDom(reqId = "unknown") {
    const pageCheck = inspectProfilePage();
    const warnings = [];

    if (!pageCheck.isProfileUrl) {
      return {
        success: false,
        error: "NOT_ON_PROFILE_PAGE",
        message: "The active tab is not a LinkedIn profile page (URL should contain /in/)."
      };
    }

    // 1. Name & Photo
    let name = "";
    const nameEl = document.querySelector(
      'h1.text-heading-xlarge, ' +
      'h1.inline.t-24, ' +
      'main h1, ' +
      '.pv-top-card--list h1, ' +
      '.artdeco-entity-lockup__title, ' +
      '.pv-text-details__left-panel h1'
    );
    if (nameEl) {
      name = cleanText(nameEl.innerText);
    }
    if (!name && document.title && document.title.includes('|')) {
      const titleCandidate = document.title.split('|')[0].trim();
      if (!titleCandidate.toLowerCase().includes('linkedin') && !titleCandidate.toLowerCase().includes('feed')) {
        name = titleCandidate;
      }
    }

    let photoUrl = "";
    const photoEl = document.querySelector(
      'img.pv-top-card-profile-picture__image, ' +
      'img.pv-top-card__photo, ' +
      '.pv-top-card__photo img, ' +
      '.presence-entity__image, ' +
      'img[alt*="profile picture"], ' +
      'img[alt*="photo"]'
    );
    if (photoEl && photoEl.src && !photoEl.src.includes('data:image')) {
      photoUrl = photoEl.src;
    }

    // 2. Headline
    let headline = "";
    const headlineEl = document.querySelector(
      '.text-body-medium.break-words, ' +
      '.pv-text-details__left-panel .text-body-medium, ' +
      'div[data-generated-suggestion-target], ' +
      '.pv-top-card--list-bullet .text-body-medium'
    );
    if (headlineEl) {
      headline = cleanText(headlineEl.innerText);
    }

    // 3. Location
    let location = "";
    const locationEl = document.querySelector(
      '.text-body-small.inline.t-black--light.break-words, ' +
      '.pv-text-details__left-panel span.text-body-small, ' +
      '.pv-top-card--list-bullet + span, ' +
      'span.text-body-small[class*="secondary"]'
    );
    if (locationEl) {
      location = cleanText(locationEl.innerText);
    }

    // Helper: Find section container by matching heading text or anchor ID
    function findSection(keywords, anchorId) {
      // 1. Try finding by anchor ID directly or parent section
      if (anchorId) {
        const anchorEl = document.getElementById(anchorId);
        if (anchorEl) {
          const parentSec = anchorEl.closest('section');
          if (parentSec) return parentSec;
          const parentDiv = anchorEl.closest('.artdeco-card');
          if (parentDiv) return parentDiv;
        }
      }

      // 2. Try section/div with id containing anchorId or keyword
      if (anchorId) {
        const secById = document.querySelector(`section[id*="${anchorId}" i], div[id*="${anchorId}" i], [data-section*="${anchorId}" i]`);
        if (secById) {
          const directSec = secById.tagName === 'SECTION' ? secById : (secById.closest('section') || secById);
          if (directSec) return directSec;
        }
      }

      // 3. Scan all sections and artdeco cards in main / document
      const allSections = document.querySelectorAll('main section, section, .artdeco-card, [data-view-name*="profile"]');
      for (const sec of allSections) {
        const headerEls = sec.querySelectorAll('h2, .pvs-header__title, header, .pvs-header__container, [data-field="title"], span.text-heading-large');
        for (const header of headerEls) {
          const hText = (header.innerText || header.textContent || "").toLowerCase().trim();
          if (keywords.some(k => hText.includes(k))) {
            return sec;
          }
        }
      }
      return null;
    }

    // 4. About Section
    let about = "";
    const aboutSec = findSection(["about", "summary"], "about");
    if (aboutSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: about section found`);
      expandSeeMoreButtons(aboutSec, "about");
      const aboutTextEl = aboutSec.querySelector(
        '.inline-show-more-text, ' +
        '[data-field="about"], ' +
        '.pv-about__summary-text, ' +
        '.display-flex.ph5.pv3 span[aria-hidden="true"], ' +
        '.pv-shared-text-with-see-more span, ' +
        '.text-body-medium span'
      );
      if (aboutTextEl) {
        about = cleanText(aboutTextEl.innerText);
      } else {
        const allSpans = Array.from(aboutSec.querySelectorAll('span[aria-hidden="true"]'))
          .map(s => cleanText(s.innerText))
          .filter(t => t && !t.toLowerCase().includes('about') && !t.toLowerCase().includes('see more'));
        if (allSpans.length > 0) {
          about = allSpans.join("\n");
        } else {
          const allText = cleanText(aboutSec.innerText);
          about = allText.replace(/^(about|summary)\s*/i, "");
        }
      }
    } else {
      warnings.push("About section was not found on the visible profile page.");
    }

    // 5. Experience Section
    const experience = [];
    const expSec = findSection(["experience", "work experience"], "experience");
    if (expSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: experience section found`);
      expandSeeMoreButtons(expSec, "experience");
      const items = expSec.querySelectorAll(
        'li.artdeco-list__item, ' +
        'li.pvs-list__item, ' +
        '.pvs-entity, ' +
        'li[class*="experience"], ' +
        'div[data-view-name="profile-component-entity"]'
      );
      items.forEach(item => {
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex, span.visually-hidden'))
          .map(el => cleanText(el.innerText || el.textContent))
          .filter(t => t && !t.toLowerCase().includes('show all') && !t.toLowerCase().includes('skills:'));

        const uniqueLines = [];
        lines.forEach(l => {
          if (!uniqueLines.includes(l)) uniqueLines.push(l);
        });

        if (uniqueLines.length > 0) {
          const title = uniqueLines[0] || "";
          const company = uniqueLines.length > 1 ? uniqueLines[1] : "";
          const dates = uniqueLines.length > 2 ? uniqueLines[2] : "";
          const expLocation = uniqueLines.length > 3 && !uniqueLines[3].includes("·") ? uniqueLines[3] : "";
          const desc = uniqueLines.slice(3).join("\n");

          if (title && title.length < 150) {
            experience.push({
              title,
              company,
              start_date: dates,
              location: expLocation,
              description: desc
            });
          }
        }
      });
    } else {
      warnings.push("Experience section was not found on the visible profile page.");
    }

    // 6. Education Section
    const education = [];
    const eduSec = findSection(["education"], "education");
    if (eduSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: education section found`);
      expandSeeMoreButtons(eduSec, "education");
      const items = eduSec.querySelectorAll(
        'li.artdeco-list__item, ' +
        'li.pvs-list__item, ' +
        '.pvs-entity, ' +
        'li[class*="education"], ' +
        'div[data-view-name="profile-component-entity"]'
      );
      items.forEach(item => {
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex, span.visually-hidden'))
          .map(el => cleanText(el.innerText || el.textContent))
          .filter(t => t && !t.toLowerCase().includes('show all'));

        const uniqueLines = [];
        lines.forEach(l => {
          if (!uniqueLines.includes(l)) uniqueLines.push(l);
        });

        if (uniqueLines.length > 0) {
          education.push({
            school: uniqueLines[0] || "",
            degree: uniqueLines.length > 1 ? uniqueLines[1] : "",
            field_of_study: uniqueLines.length > 2 ? uniqueLines[2] : "",
            dates: uniqueLines.length > 3 ? uniqueLines[3] : ""
          });
        }
      });
    }

    // 7. Skills Section
    const skills = [];
    const skillsSec = findSection(["skills"], "skills");
    if (skillsSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: skills section found`);
      expandSeeMoreButtons(skillsSec, "skills");
      const items = skillsSec.querySelectorAll(
        'li.artdeco-list__item, ' +
        'li.pvs-list__item, ' +
        '.pvs-entity, ' +
        'li[class*="skill"], ' +
        'div[data-view-name="profile-component-entity"], ' +
        '.hoverable-link-text'
      );
      items.forEach(item => {
        const sNameEl = item.querySelector('span[aria-hidden="true"], a');
        const sName = cleanText(sNameEl ? sNameEl.innerText : item.innerText);
        if (sName && sName.length < 80 && !sName.toLowerCase().includes('show all') && !sName.toLowerCase().includes('endorse')) {
          if (!skills.includes(sName)) {
            skills.push(sName);
          }
        }
      });
    }

    // 8. Certifications Section
    const certifications = [];
    const certSec = findSection(["licenses & certifications", "certifications", "licenses"], "certifications");
    if (certSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: certifications section found`);
      expandSeeMoreButtons(certSec, "certifications");
      const items = certSec.querySelectorAll(
        'li.artdeco-list__item, ' +
        'li.pvs-list__item, ' +
        '.pvs-entity, ' +
        'div[data-view-name="profile-component-entity"]'
      );
      items.forEach(item => {
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex'))
          .map(el => cleanText(el.innerText))
          .filter(Boolean);
        if (lines.length > 0) {
          certifications.push({
            name: lines[0] || "",
            authority: lines.length > 1 ? lines[1] : "",
            issued: lines.length > 2 ? lines[2] : ""
          });
        }
      });
    }

    // Current position inference
    let current_position = "";
    if (experience.length > 0) {
      const firstExp = experience[0];
      current_position = firstExp.company ? `${firstExp.title} @ ${firstExp.company}` : firstExp.title;
    } else if (headline) {
      current_position = headline.split('|')[0].trim();
    }

    const sectionsCount = [
      name, headline, about,
      experience.length > 0,
      education.length > 0,
      skills.length > 0,
      certifications.length > 0
    ].filter(Boolean).length;

    console.log(`[LinkedIn Content] Extracted summary:`, {
      name: !!name,
      headline: !!headline,
      about: !!about,
      experience: experience.length,
      education: education.length,
      skills: skills.length,
      certifications: certifications.length
    });

    const isVisible = document.visibilityState === "visible";
    const scrollHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 0);

    const diagnostic = {
      requestId: reqId,
      version: EXTENSION_CONTENT_VERSION,
      pageVisibility: isVisible,
      path: window.location.pathname,
      scrollHeight: scrollHeight,
      sectionsDiscovered: sectionsCount,
      extractedCounts: {
        experience: experience.length,
        education: education.length,
        skills: skills.length,
        certifications: certifications.length,
        hasAbout: !!about,
        hasName: !!name,
        hasHeadline: !!headline
      },
      status: sectionsCount >= 3 ? "complete" : (sectionsCount > 0 ? "partial" : "failed")
    };

    return {
      success: true,
      data: {
        name,
        headline,
        about,
        location,
        current_position,
        profile_url: pageCheck.currentUrl,
        vanity_name: pageCheck.vanityName,
        profile_photo_url: photoUrl,
        experience,
        education,
        skills,
        certifications
      },
      metadata: {
        sections_found: sectionsCount,
        is_self_profile_likely: pageCheck.isSelfProfileLikely,
        extracted_at: new Date().toISOString(),
        warnings: warnings,
        diagnostic: diagnostic
      }
    };
  }

  // Extract detail list items from single-purpose detail pages (/in/me/details/<kind>/)
  function extractDetailListPage(kind) {
    const listItems = [];
    const normalizedKind = (kind || "").toLowerCase().trim();

    // Check for login redirect, 404, or empty placeholder
    const isLogin = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
    if (isLogin) {
      return { success: false, error: "SESSION_EXPIRED", items: [] };
    }

    // In detail pages, entries are typically rendered in an artdeco list or pvs-list
    const container = document.querySelector('main ul.pvs-list, main .artdeco-card ul, main [data-view-name*="profile"] ul, ul.artdeco-list, main ul');
    const elements = container ? container.querySelectorAll('li.pvs-list__item, li.artdeco-list__item, li') : document.querySelectorAll('main li.pvs-list__item, main li.artdeco-list__item');

    if (normalizedKind === "experience") {
      elements.forEach(item => {
        expandSeeMoreButtons(item, "detail_experience");
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex, span.visually-hidden'))
          .map(el => cleanText(el.innerText || el.textContent))
          .filter(t => t && !t.toLowerCase().includes('show all') && !t.toLowerCase().includes('skills:'));

        const uniqueLines = [];
        lines.forEach(l => {
          if (!uniqueLines.includes(l)) uniqueLines.push(l);
        });

        if (uniqueLines.length > 0) {
          const title = uniqueLines[0] || "";
          const company = uniqueLines.length > 1 ? uniqueLines[1] : "";
          const dates = uniqueLines.length > 2 ? uniqueLines[2] : "";
          const expLocation = uniqueLines.length > 3 && !uniqueLines[3].includes("·") ? uniqueLines[3] : "";
          const desc = uniqueLines.slice(3).join("\n");

          if (title && title.length < 150) {
            listItems.push({
              title,
              company,
              start_date: dates,
              location: expLocation,
              description: desc
            });
          }
        }
      });
    } else if (normalizedKind === "education") {
      elements.forEach(item => {
        expandSeeMoreButtons(item, "detail_education");
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex, span.visually-hidden'))
          .map(el => cleanText(el.innerText || el.textContent))
          .filter(t => t && !t.toLowerCase().includes('show all'));

        const uniqueLines = [];
        lines.forEach(l => {
          if (!uniqueLines.includes(l)) uniqueLines.push(l);
        });

        if (uniqueLines.length > 0) {
          listItems.push({
            school: uniqueLines[0] || "",
            degree: uniqueLines.length > 1 ? uniqueLines[1] : "",
            field_of_study: uniqueLines.length > 2 ? uniqueLines[2] : "",
            dates: uniqueLines.length > 3 ? uniqueLines[3] : ""
          });
        }
      });
    } else if (normalizedKind === "skills") {
      elements.forEach(item => {
        const sNameEl = item.querySelector('span[aria-hidden="true"], a, div.hoverable-link-text');
        const sName = cleanText(sNameEl ? sNameEl.innerText : item.innerText);
        if (sName && sName.length < 80 && !sName.toLowerCase().includes('show all') && !sName.toLowerCase().includes('endorse')) {
          if (!listItems.includes(sName)) {
            listItems.push(sName);
          }
        }
      });
    } else if (normalizedKind === "certifications") {
      elements.forEach(item => {
        expandSeeMoreButtons(item, "detail_certifications");
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex'))
          .map(el => cleanText(el.innerText))
          .filter(Boolean);
        if (lines.length > 0) {
          listItems.push({
            name: lines[0] || "",
            authority: lines.length > 1 ? lines[1] : "",
            issued: lines.length > 2 ? lines[2] : ""
          });
        }
      });
    }

    return {
      success: true,
      kind: normalizedKind,
      count: listItems.length,
      items: listItems
    };
  }

  // Check if an anchor element represents an anonymized "LinkedIn Member" search result card/title
  function isAnonymousMemberTitleAnchor(anchor) {
    if (!anchor || anchor.tagName !== 'A') return false;

    // Must not be inside global navigation, header, footer, aside, pagination, etc.
    if (anchor.closest('header, nav, footer, aside, .artdeco-pagination, [role="navigation"], #global-nav, .feed-identity-module')) {
      return false;
    }

    // A candidate anonymous anchor's own destination must NOT be an individual verified profile (/in/<slug>)
    const href = anchor.href || anchor.getAttribute('href') || '';
    if (href.includes('/in/') && !href.includes('/in/unavailable') && !href.includes('/in/me')) {
      const clean = href.split('?')[0].replace(/\/+$/, '');
      const handle = clean.split('/in/')[1];
      if (handle && !['feed', 'mynetwork', 'jobs', 'messaging', 'notifications'].includes(handle.toLowerCase())) {
        return false;
      }
    }

    // 1. Direct match: Check if anchor's own normalized visible text is exactly "LinkedIn Member"
    // (e.g. title-specific anchor with aria-hidden span or compact text)
    const ariaSpan = anchor.querySelector('span[aria-hidden="true"]');
    const directRawText = ariaSpan ? (ariaSpan.innerText || ariaSpan.textContent || '') : (anchor.innerText || anchor.textContent || '');
    if (cleanText(directRawText).toLowerCase() === 'linkedin member') {
      return true;
    }

    // 2. Descendant identity element match: When an outer anchor wraps the entire result card
    // (where anchor.innerText contains "LinkedIn Member" plus headline, location, experience, etc.),
    // inspect descendant elements (e.g. <p>, <span>, <div>, <h1>-<h6>) for an exact identity label.
    const candidateIdentityDescendants = anchor.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6');
    for (const el of candidateIdentityDescendants) {
      // Ignore elements that contain further block children to ensure we check the leaf/identity node
      const hasBlockChildren = !!el.querySelector('p, div, ul, ol, section');
      if (hasBlockChildren) continue;

      const raw = el.innerText || el.textContent || '';
      if (cleanText(raw).toLowerCase() === 'linkedin member') {
        return true;
      }
    }

    return false;
  }

  // Extract unverified market signals from an anonymous "LinkedIn Member" card or outer card anchor
  function extractAnonymousCardSignal(cardOrAnchor, queryContext = {}) {
    if (!cardOrAnchor) return null;

    // 1. Visible Headline / Role
    let headline = "";
    const subtitleEl = cardOrAnchor.querySelector(
      '.entity-result__primary-subtitle, ' +
      'div[class*="primary-subtitle"], ' +
      'div[class*="actor__title"] ~ div, ' +
      'p[class*="headline"], ' +
      'p.headline, ' +
      'div.t-14.t-black.t-normal, ' +
      'p[class*="subtitle"], ' +
      'div[class*="subline"]'
    );
    if (subtitleEl) {
      headline = cleanText(subtitleEl.innerText || subtitleEl.textContent);
    }

    // 2. Visible Location
    let location = "";
    const locationEl = cardOrAnchor.querySelector(
      '.entity-result__secondary-subtitle, ' +
      'div[class*="secondary-subtitle"], ' +
      'div.t-14.t-normal.t-black--light, ' +
      'p[class*="location"], ' +
      'p.location, ' +
      'div[class*="caption"]'
    );
    if (locationEl) {
      location = cleanText(locationEl.innerText || locationEl.textContent);
    }

    // 3. Visible Experience Snippet
    let experienceSnippet = "";
    const summarySnippet = cardOrAnchor.querySelector(
      '.entity-result__summary, ' +
      'p[class*="summary"], ' +
      'p[class*="entity-result"], ' +
      'div[class*="experience"], ' +
      'div.experience'
    );
    if (summarySnippet) {
      experienceSnippet = cleanText(summarySnippet.innerText || summarySnippet.textContent);
    }

    // 4. Fallback for outer card anchor containing paragraphs if specific selectors were not found
    if (!headline || !location || !experienceSnippet) {
      const allParagraphs = cardOrAnchor.querySelectorAll('p, div.t-14');
      for (const p of allParagraphs) {
        // Skip child wrappers that contain nested paragraphs
        if (p.querySelector('p')) continue;
        const text = cleanText(p.innerText || p.textContent);
        if (!text || text.toLowerCase() === 'linkedin member') continue;

        // Skip connection degree badges or member directory noise
        if (/^(1st|2nd|3rd\+?|·\s*(1st|2nd|3rd\+?))$/i.test(text)) continue;

        if (!headline && (text.includes('@') || text.includes('Founder') || text.includes('CEO') || text.includes('VP') || text.includes('Director') || text.includes('Manager') || text.includes('Lead') || text.includes('Engineer') || text.includes('Sales') || text.includes('Head of') || text.length > 5)) {
          // If headline is not set yet, use the first substantive non-identity text
          headline = text;
        } else if (!location && (text.includes(',') || text.includes('Area') || text.includes('India') || text.includes('United States') || text.includes('Bengaluru') || text.includes('London'))) {
          location = text;
        } else if (!experienceSnippet && (text.includes('Current:') || text.includes('Past:') || text.includes('Experience:'))) {
          experienceSnippet = text;
        }
      }
    }

    // 5. Extract Explicit Company Mentions from headline and experience snippet
    const companyMentions = new Set();
    const parseCompany = (txt) => {
      if (!txt) return;
      if (txt.includes(" at ")) {
        const parts = txt.split(" at ");
        if (parts.length > 1) {
          const comp = parts[1].split(/[·•|,\n]/)[0].trim();
          if (comp && comp.length < 60) companyMentions.add(comp);
        }
      }
      if (txt.includes(" @ ")) {
        const parts = txt.split(" @ ");
        if (parts.length > 1) {
          const comp = parts[1].split(/[·•|,\n]/)[0].trim();
          if (comp && comp.length < 60) companyMentions.add(comp);
        }
      } else if (txt.includes("@")) {
        const match = txt.match(/@\s*([A-Za-z0-9&.\-_ ]+)/);
        if (match && match[1]) {
          const comp = match[1].split(/[·•|,\n]/)[0].trim();
          if (comp && comp.length < 60 && comp.length > 1) companyMentions.add(comp);
        }
      }
      const curMatch = txt.match(/Current:\s*([^·•\n]+)/i);
      if (curMatch && curMatch[1]) {
        const comp = curMatch[1].trim();
        if (comp && comp.length < 60) companyMentions.add(comp);
      }
    };

    parseCompany(headline);
    parseCompany(experienceSnippet);

    // Apply sensible bounds and sanitization
    headline = headline ? headline.substring(0, 300).trim() : "";
    location = location ? location.substring(0, 150).trim() : "";
    experienceSnippet = experienceSnippet ? experienceSnippet.substring(0, 300).trim() : "";

    // Must have at least some visible professional text to be a valid signal
    if (!headline && !location && !experienceSnippet) {
      return null;
    }

    return {
      headline: headline || "-",
      location: location || "-",
      experience_snippet: experienceSnippet || "-",
      company_mentions: Array.from(companyMentions).slice(0, 5),
      source_query: queryContext.queryText || queryContext.queryId || ""
    };
  }

  // Count and extract total distinct anonymous "LinkedIn Member" title anchors and their signals
  function getAnonymousMemberSignals(queryContext = {}) {
    const mainEl = document.querySelector('main, [role="main"], .scaffold-layout__main') || document.body;
    if (!mainEl) return { count: 0, signals: [] };

    // Search for all anchors within main search area
    const anchors = mainEl.querySelectorAll('a');
    const distinctAnonymousAnchors = new Set();
    const signals = [];
    const seenSignalKeys = new Set();

    for (const a of anchors) {
      if (isAnonymousMemberTitleAnchor(a)) {
        distinctAnonymousAnchors.add(a);
        const cardOrAnchor = findSearchResultCard(a) || a;
        const signal = extractAnonymousCardSignal(cardOrAnchor, queryContext);
        if (signal) {
          // Deduplicate signals by normalized headline + location
          const sigKey = `${signal.headline.toLowerCase()}|${signal.location.toLowerCase()}|${signal.experience_snippet.toLowerCase()}`;
          if (!seenSignalKeys.has(sigKey)) {
            seenSignalKeys.add(sigKey);
            signals.push(signal);
          }
        }
      }
    }

    return {
      count: distinctAnonymousAnchors.size,
      signals: signals
    };
  }

  // Count total distinct anonymous "LinkedIn Member" title anchors visible in main search results
  // Identifies candidate title anchors directly without relying on fragile multi-level ancestor containers.
  function countAnonymousMemberCards() {
    const mainEl = document.querySelector('main, [role="main"], .scaffold-layout__main') || document.body;
    if (!mainEl) return 0;

    // Search for all anchors within main search area
    const anchors = mainEl.querySelectorAll('a');
    const distinctAnonymousAnchors = new Set();

    for (const a of anchors) {
      if (isAnonymousMemberTitleAnchor(a)) {
        distinctAnonymousAnchors.add(a);
      }
    }

    return distinctAnonymousAnchors.size;
  }

  // Helper: Determine if an anchor element is a legitimate search result candidate link
  function isSearchResultProfileAnchor(anchor) {
    if (!anchor || !anchor.href) return false;
    const href = anchor.href;

    // Must be a LinkedIn profile link (/in/...)
    if (!href.includes('/in/')) return false;

    // Filter out common non-result paths
    const clean = href.split('?')[0].replace(/\/+$/, '');
    if (clean.endsWith('/in') || clean.includes('/in/unavailable') || clean.includes('/in/me')) return false;

    // Filter out self-profile link, global header, navigation bar, sidebar identity module, footer, and aside elements
    if (anchor.closest('header, nav, #global-nav, .global-nav, .feed-identity-module, aside, footer, [role="navigation"], [role="banner"]')) {
      return false;
    }

    // Do NOT reject links based on rect.width === 0 or rect.height === 0 or empty text content
    // as dynamic virtualized containers often have unmeasured bounds before scroll/hydration.

    return true;
  }

  // Helper: Find the closest bounding search card container for a profile anchor
  function findSearchResultCard(anchor) {
    if (!anchor) return null;

    // 1. Check known container tags / classes in modern and legacy LinkedIn DOM
    const knownCard = anchor.closest(
      'li.reusable-search__result-container, ' +
      'li[class*="reusable-search"], ' +
      'div[data-view-name="search-entity-result-universal-template"], ' +
      'div[data-view-name*="entity-result"], ' +
      'div[data-chameleon-result-urn], ' +
      'div.entity-result, ' +
      'div.entity-result__item, ' +
      'div[class*="entity-result"], ' +
      'ul.reusable-search__entity-result-list > li, ' +
      '.search-results-container li, ' +
      'div.artdeco-card'
    );
    if (knownCard) return knownCard;

    // 2. Climb ancestors looking for a container that represents a single entity card
    // Avoid treating the entire page, main, or shared ul list wrapper as one card
    let curr = anchor.parentElement;
    let depth = 0;
    while (curr && depth < 6) {
      const tag = curr.tagName;
      if (tag === 'LI') return curr;
      if (tag === 'MAIN' || tag === 'BODY' || tag === 'UL' || tag === 'OL' || curr.getAttribute('role') === 'main' || curr.className.includes('search-results-container')) {
        break;
      }

      // Check if this container contains typical card child elements
      const hasSubtitle = !!curr.querySelector('[class*="subtitle"], [class*="summary"], [class*="headline"], [class*="caption"], p, div.t-14');
      const textLen = (curr.innerText || "").trim().length;
      if (textLen > 15 && hasSubtitle) {
        return curr;
      }
      curr = curr.parentElement;
      depth++;
    }

    return anchor.parentElement || anchor;
  }

  // Wait for LinkedIn search results DOM to finish rendering
  async function waitForSearchResultsRender(maxRetries = 15, intervalMs = 400) {
    let attempts = 0;
    while (attempts < maxRetries) {
      attempts++;

      const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
      if (isLoginPage) {
        return { status: "LOGIN_REQUIRED", error: "SESSION_EXPIRED", message: "LinkedIn redirected to login page." };
      }

      const isChallenge = !!document.querySelector('#captcha-internal, .challenge-dialog, iframe[src*="challenge"], [data-control-name="challenge"]');
      if (isChallenge) {
        return { status: "CHECKPOINT_DETECTED", error: "CHALLENGE_DETECTED", message: "LinkedIn security challenge or checkpoint detected." };
      }

      // Check for zero-results empty state rendered by LinkedIn
      const emptyStateEl = document.querySelector('.search-empty-state, .artdeco-empty-state, .search-results-container .artdeco-empty-state__headline, [class*="empty-state"]');
      const emptyText = emptyStateEl ? (emptyStateEl.textContent || "").toLowerCase() : "";
      if (emptyText.includes("no results") || emptyText.includes("no matching") || emptyText.includes("try searching for something else")) {
        console.log(`[LinkedIn Content] SEARCH_EMPTY_STATE_DETECTED after ${attempts * intervalMs}ms`);
        return { status: "EMPTY_RESULTS", emptyState: true, attempts };
      }

      // 1. Check for presence of search results containers or result cards
      const hasResultCards = !!document.querySelector(
        'li.reusable-search__result-container, ' +
        'div[data-view-name="search-entity-result-universal-template"], ' +
        'div[data-chameleon-result-urn], ' +
        '.search-results-container li, ' +
        'ul.reusable-search__entity-result-list > li, ' +
        'div.entity-result, ' +
        'div.entity-result__item, ' +
        'div[class*="entity-result"], ' +
        'a[data-view-name="search-result-lockup-title"], ' +
        'span.entity-result__title-text a'
      );

      // 2. Fallback check: Check for any profile anchors inside main search area
      const allInAnchors = Array.from(document.querySelectorAll('a[href*="/in/"]'));
      const validCandidateAnchors = allInAnchors.filter(isSearchResultProfileAnchor);

      // 3. Anonymous cards check: Detect if cards exist even if names are masked as "LinkedIn Member"
      const anonCardsCount = countAnonymousMemberCards();

      if (hasResultCards || validCandidateAnchors.length > 0 || anonCardsCount > 0) {
        console.log(`[LinkedIn Content] SEARCH_RESULTS_RENDERED detected after ${attempts * intervalMs}ms (cards=${hasResultCards}, validInLinks=${validCandidateAnchors.length}, anonCards=${anonCardsCount})`);
        return {
          status: "RESULTS_READY",
          emptyState: false,
          attempts,
          hasResultCards,
          candidateLinkCount: validCandidateAnchors.length,
          anonymousCardsCount: anonCardsCount
        };
      }

      // Scroll slightly during waiting to trigger viewport intersection observers
      if (attempts === 2 || attempts === 5 || attempts === 8) {
        window.scrollBy({ top: 250, behavior: 'smooth' });
      }

      await new Promise(r => setTimeout(r, intervalMs));
    }

    console.warn(`[LinkedIn Content] SEARCH_RENDER_TIMEOUT reached after ${maxRetries * intervalMs}ms`);
    return { status: "RENDER_TIMEOUT", attempts: maxRetries };
  }

  // Extract visible search results from LinkedIn people search DOM with thorough DOM diagnostics
  function extractSearchResultsDom(queryContext = {}) {
    const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
    if (isLoginPage) {
      return {
        success: false,
        status: "LOGIN_REQUIRED",
        error: "SESSION_EXPIRED",
        message: "LinkedIn redirected to sign-in page.",
        results: [],
        count: 0
      };
    }

    const isChallenge = !!document.querySelector('#captcha-internal, .challenge-dialog, iframe[src*="challenge"], [data-control-name="challenge"]');
    if (isChallenge) {
      return {
        success: false,
        status: "CHECKPOINT_DETECTED",
        error: "CHALLENGE_DETECTED",
        message: "LinkedIn verification challenge detected.",
        results: [],
        count: 0
      };
    }

    // Comprehensive DOM Telemetry (no personal information captured)
    const currentHref = window.location.href;
    const isSearchRoute = currentHref.includes('/search/results/');
    const isPeopleSearchRoute = currentHref.includes('/search/results/people/');

    const emptyStateEl = document.querySelector('.search-empty-state, .artdeco-empty-state, .search-results-container .artdeco-empty-state__headline, [class*="empty-state"]');
    const emptyText = emptyStateEl ? (emptyStateEl.textContent || "").toLowerCase() : "";
    const isExplicitNoResults = emptyText.includes("no results") || emptyText.includes("no matching") || emptyText.includes("try searching for something else");

    const telemetry = {
      href: currentHref.split('#')[0],
      pathname: window.location.pathname,
      title: document.title || "",
      readyState: document.readyState || "",
      visibilityState: document.visibilityState || "",
      bodyTextLength: document.body ? (document.body.innerText || "").length : 0,
      hasMainTag: !!document.querySelector("main"),
      hasRoleMain: !!document.querySelector('[role="main"]'),
      isLoginPage: isLoginPage,
      isChallenge: isChallenge,
      isExplicitNoResults: isExplicitNoResults,
      emptyTextSample: emptyText ? emptyText.substring(0, 100) : "",
      counts: {
        reusable_container: document.querySelectorAll('li.reusable-search__result-container').length,
        universal_template: document.querySelectorAll('div[data-view-name="search-entity-result-universal-template"]').length,
        chameleon_urn: document.querySelectorAll('[data-chameleon-result-urn]').length,
        entity_result: document.querySelectorAll('div.entity-result, .entity-result__item').length,
        search_results_container_li: document.querySelectorAll('.search-results-container li').length,
        reusable_entity_list_li: document.querySelectorAll('ul.reusable-search__entity-result-list > li').length,
        search_lockup_title: document.querySelectorAll('a[data-view-name="search-result-lockup-title"]').length,
        entity_title_text_a: document.querySelectorAll('span.entity-result__title-text a').length,
        all_in_anchors: document.querySelectorAll('a[href*="/in/"]').length,
        all_data_view_name: document.querySelectorAll('[data-view-name]').length
      },
      dom_sample: [] // Sanitized tag and class tree of top main container
    };

    // Sample sanitized top-level children of main or search container
    try {
      const mainEl = document.querySelector('main, [role="main"]') || document.body;
      if (mainEl) {
        const topChildren = Array.from(mainEl.children).slice(0, 8);
        telemetry.dom_sample = topChildren.map(el => ({
          tag: el.tagName,
          classes: (el.className && typeof el.className === 'string') ? el.className.split(' ').slice(0, 4).join(' ') : "",
          dataViewName: el.getAttribute('data-view-name') || null,
          role: el.getAttribute('role') || null,
          childCount: el.children.length
        }));
      }
    } catch (e) {}

    console.log(`[LinkedIn DOM Telemetry] Detailed page snapshot:`, telemetry);

    const results = [];
    const seenUrls = new Set();
    const allRawAnchors = Array.from(document.querySelectorAll('a[href*="/in/"]'));
    const allProfileAnchors = allRawAnchors.filter(isSearchResultProfileAnchor);

    // Detect count of anonymous "LinkedIn Member" result cards and extract their visible unverified signals
    const anonSignalsData = getAnonymousMemberSignals(queryContext);
    const anonymousCardsCount = anonSignalsData.count;
    const unverifiedSignals = anonSignalsData.signals;

    const diagnostic = {
      telemetry: telemetry,
      selectors_checked: [],
      matched_selector: null,
      raw_anchors_count: allRawAnchors.length,
      accepted_anchors_count: allProfileAnchors.length,
      rejected_anchors_count: allRawAnchors.length - allProfileAnchors.length,
      resolved_cards_count: 0,
      extracted_candidates_count: 0,
      discarded_anonymous: 0,
      anonymous_cards_count: anonymousCardsCount,
      unverified_signals_count: unverifiedSignals.length,
      discarded_non_profile: 0,
      is_explicit_no_results: isExplicitNoResults
    };

    // Multi-Strategy Card & Anchor Discovery:
    // Strategy A: Direct card container elements
    const itemSelectors = [
      'li.reusable-search__result-container',
      'div[data-view-name="search-entity-result-universal-template"]',
      'div[data-view-name*="entity-result"]',
      'div[data-chameleon-result-urn]',
      'ul.reusable-search__entity-result-list > li',
      '.search-results-container li',
      'div.entity-result',
      'div.entity-result__item'
    ];

    let items = [];
    for (const sel of itemSelectors) {
      diagnostic.selectors_checked.push(sel);
      const candidates = document.querySelectorAll(sel);
      if (candidates && candidates.length > 0) {
        items = Array.from(candidates);
        diagnostic.matched_selector = sel;
        diagnostic.resolved_cards_count = items.length;
        break;
      }
    }

    // Strategy B: Query result cards inside main landmark or search scaffold
    if (items.length === 0) {
      const mainSearchEl = document.querySelector('main, .search-results-container, .scaffold-layout__main, [role="main"]');
      if (mainSearchEl) {
        const potentialCards = mainSearchEl.querySelectorAll('.entity-result__item, div[class*="entity-result"], div[data-chameleon-result-urn], li[class*="reusable-search"]');
        if (potentialCards && potentialCards.length > 0) {
          items = Array.from(potentialCards);
          diagnostic.matched_selector = 'main .entity-result__item';
          diagnostic.resolved_cards_count = items.length;
        }
      }
    }

    // Strategy C (Resilient Link Anchor Strategy):
    // Find all valid profile links (/in/...) inside the page, filter out header/nav/footer,
    // and group them by their closest bounding card container.
    if (items.length === 0 && allProfileAnchors.length > 0) {
      diagnostic.matched_selector = 'profile_anchor_card_resolution';
      const resolvedCardSet = new Set();
      const resolvedCards = [];

      for (const anc of allProfileAnchors) {
        const card = findSearchResultCard(anc);
        if (card && !resolvedCardSet.has(card)) {
          resolvedCardSet.add(card);
          resolvedCards.push(card);
        }
      }
      items = resolvedCards;
      diagnostic.resolved_cards_count = items.length;
    }

    // Extraction loop across identified items
    for (const item of items) {
      if (!item) continue;

      // 1. Profile Link and Name
      // Query name anchors inside the card
      const nameAnchor = item.querySelector(
        'a[data-view-name="search-result-lockup-title"], ' +
        'span.entity-result__title-text a.app-aware-link, ' +
        'span.entity-result__title-text a, ' +
        'a[data-control-name="search_srp_result"], ' +
        'a.app-aware-link[href*="/in/"], ' +
        'span.entity-result__title a, ' +
        'a[href*="/in/"]'
      ) || (item.tagName === 'A' && item.href ? item : null);

      if (!nameAnchor || !nameAnchor.href) {
        diagnostic.discarded_non_profile++;
        continue;
      }

      if (!isSearchResultProfileAnchor(nameAnchor)) {
        diagnostic.discarded_non_profile++;
        continue;
      }

      const rawHref = nameAnchor.href.split('?')[0].replace(/\/+$/, '');
      if (seenUrls.has(rawHref)) continue;

      // Extract Name
      let name = "";
      const nameAriaSpan = nameAnchor.querySelector('span[aria-hidden="true"]');
      if (nameAriaSpan) {
        name = cleanText(nameAriaSpan.innerText || nameAriaSpan.textContent);
      } else {
        name = cleanText(nameAnchor.innerText || nameAnchor.textContent);
      }

      // Remove "View <Name>'s profile" or similar screen reader noise
      name = name.replace(/^View\s+/i, '').replace(/['’]s\s+profile.*$/i, '').trim();
      if (!name || name.toLowerCase().includes('linkedin member')) {
        diagnostic.discarded_anonymous++;
        continue;
      }

      // 2. Connection Degree Badge
      let connectionDegree = "Unknown";
      // Inspect visible badge within the card/title lockup
      const badgeEl = item.querySelector(
        'span.entity-result__badge-text, ' +
        'span.dist-value, ' +
        'span[class*="badge"], ' +
        '.entity-result__badge, ' +
        'span.image-text-lockup__badge, ' +
        'span.t-12.t-black--light'
      );
      if (badgeEl) {
        const badgeRaw = cleanText(badgeEl.innerText || badgeEl.textContent);
        if (/^1st(\s+degree)?$/i.test(badgeRaw) || badgeRaw.includes("1st")) {
          connectionDegree = "1st";
        } else if (/^2nd(\s+degree)?$/i.test(badgeRaw) || badgeRaw.includes("2nd")) {
          connectionDegree = "2nd";
        } else if (/^3rd(\+)?(\s+degree)?$/i.test(badgeRaw) || badgeRaw.includes("3rd")) {
          connectionDegree = "3rd+";
        }
      } else {
        // Fallback: check text of title container for isolated connection markers (e.g. "· 2nd")
        const titleParent = nameAnchor.closest('.entity-result__title-line, .entity-result__title, div, li') || item;
        const textAroundName = cleanText(titleParent.innerText || titleParent.textContent || "");
        const degMatch = textAroundName.match(/[·•]\s*(1st|2nd|3rd\+?)\b/i) || textAroundName.match(/\b(1st|2nd|3rd\+?)\s+degree\b/i);
        if (degMatch && degMatch[1]) {
          const matchUpper = degMatch[1].toLowerCase();
          if (matchUpper.startsWith('1')) connectionDegree = '1st';
          else if (matchUpper.startsWith('2')) connectionDegree = '2nd';
          else if (matchUpper.startsWith('3')) connectionDegree = '3rd+';
        }
      }

      // 3. Headline / Role (Primary Subtitle)
      let headline = "";
      const subtitleEl = item.querySelector(
        '.entity-result__primary-subtitle, ' +
        'div[class*="primary-subtitle"], ' +
        '.entity-result__summary, ' +
        'div[class*="actor__title"] ~ div, ' +
        'div.t-14.t-black.t-normal, ' +
        'div.entity-result__content p, ' +
        'p[class*="subtitle"], ' +
        'div[class*="subline"]'
      );
      if (subtitleEl) {
        headline = cleanText(subtitleEl.innerText || subtitleEl.textContent);
      }

      // 3. Location (Secondary Subtitle)
      let location = "";
      const locationEl = item.querySelector(
        '.entity-result__secondary-subtitle, ' +
        'div[class*="secondary-subtitle"], ' +
        'div.t-14.t-normal.t-black--light, ' +
        'div[class*="caption"]'
      );
      if (locationEl) {
        location = cleanText(locationEl.innerText || locationEl.textContent);
      }

      // 4. Company (extract from headline or summary snippet if present)
      let company = "";
      const summarySnippet = item.querySelector('.entity-result__summary, p[class*="summary"], p[class*="entity-result"]');
      const summaryText = summarySnippet ? cleanText(summarySnippet.innerText || summarySnippet.textContent) : "";

      if (headline.includes(" at ")) {
        company = headline.split(" at ").slice(1).join(" at ").trim();
      } else if (headline.includes(" @ ")) {
        company = headline.split(" @ ").slice(1).join(" @ ").trim();
      } else if (summaryText && (summaryText.includes(" at ") || summaryText.includes("Current: "))) {
        const curMatch = summaryText.match(/Current:\s*([^·\n]+)/i);
        if (curMatch) company = curMatch[1].trim();
      }

      seenUrls.add(rawHref);
      results.push({
        name,
        role: headline,
        headline,
        company,
        location,
        connection_degree: connectionDegree,
        profile_url: rawHref,
        source_query_id: queryContext.queryId || null,
        source_query_text: queryContext.queryText || null
      });
    }

    diagnostic.extracted_candidates_count = results.length;

    const currentUrl = window.location.href.split('?')[0];

    // Determine status accurately according to exact failure taxonomy
    let status = "RESULTS_EXTRACTED";
    if (results.length === 0) {
      if (isLoginPage) {
        status = "LOGIN_REQUIRED";
      } else if (isChallenge) {
        status = "CHECKPOINT_DETECTED";
      } else if (!isSearchRoute) {
        status = "SEARCH_PAGE_NOT_LOADED";
      } else if (isExplicitNoResults) {
        status = "VERIFIED_EMPTY_RESULTS";
      } else if (anonymousCardsCount > 0) {
        // Cards rendered on page, but all prospect identities are masked as "LinkedIn Member"
        status = "ANONYMOUS_OUT_OF_NETWORK_RESULTS";
      } else if (allProfileAnchors.length === 0 && telemetry.counts.reusable_container === 0 && telemetry.counts.universal_template === 0 && telemetry.counts.entity_result === 0) {
        // No containers, no anonymous cards, AND no valid candidate profile links found anywhere on the page
        status = "SEARCH_RESULTS_NOT_RENDERED";
      } else if (allProfileAnchors.length > 0 && items.length === 0) {
        // Valid candidate links exist, but card resolution failed
        status = "RESULTS_PRESENT_SELECTOR_MISMATCH";
      } else if (items.length > 0 && results.length === 0) {
        // Containers were located or resolved, but card data extraction failed
        status = "RESULTS_PRESENT_BUT_EXTRACTION_FAILED";
      } else {
        status = "NO_RESULT_CONTAINERS_FOUND";
      }
    }

    return {
      success: results.length > 0 || unverifiedSignals.length > 0,
      status: status,
      count: results.length,
      currentUrl: currentUrl,
      queryContext: queryContext,
      results: results,
      unverified_signals: unverifiedSignals,
      diagnostic: diagnostic
    };
  }

  // Message listener function stored on window to allow cleanup on re-injection
  window.__famewebLinkedInMessageListener = function(request, sender, sendResponse) {
    if (!request || typeof request !== "object") return;

    if (request.action === "PING") {
      sendResponse({ status: "PONG", version: EXTENSION_CONTENT_VERSION, url: window.location.href.split('?')[0] });
      return true;
    }

    if (request.action === "CHECK_DOM_AUTH") {
      const isAuth = checkDomAuthState();
      const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
      const isChallenge = !!document.querySelector('#captcha-internal, .challenge-dialog, iframe[src*="challenge"], [data-control-name="challenge"]');
      sendResponse({
        authenticated: isAuth,
        isLoginPage,
        isChallenge,
        currentUrl: window.location.href.split('?')[0]
      });
      return true;
    }

    if (request.action === "DISCOVER_OWN_PROFILE") {
      const isAuth = checkDomAuthState();
      const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
      const isChallenge = !!document.querySelector('#captcha-internal, .challenge-dialog, iframe[src*="challenge"], [data-control-name="challenge"]');

      if (!isAuth || isLoginPage) {
        sendResponse({
          success: false,
          error: "NOT_AUTHENTICATED",
          isLoginPage: true,
          message: "LinkedIn tab is not logged in. Please sign in to LinkedIn."
        });
        return true;
      }

      if (isChallenge) {
        sendResponse({
          success: false,
          error: "CHALLENGE_DETECTED",
          message: "LinkedIn is presenting a security or verification challenge. Please resolve it in the LinkedIn tab."
        });
        return true;
      }

      const discovery = discoverOwnProfileUrl();
      const pageCheck = inspectProfilePage();
      sendResponse({
        success: true,
        authenticated: true,
        profileUrl: discovery.url,
        discoveryMethod: discovery.method,
        currentPage: pageCheck
      });
      return true;
    }

    if (request.action === "WAIT_FOR_PROFILE_RENDER") {
      const maxRetries = request.maxRetries || 10;
      const intervalMs = request.intervalMs || 500;
      let attempts = 0;

      const checkRenderInterval = setInterval(() => {
        attempts++;
        const isAuth = checkDomAuthState();
        const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
        const isChallenge = !!document.querySelector('#captcha-internal, .challenge-dialog, iframe[src*="challenge"]');

        if (isLoginPage) {
          clearInterval(checkRenderInterval);
          sendResponse({ success: false, error: "SESSION_EXPIRED", message: "Redirected to login page." });
          return;
        }

        if (isChallenge) {
          clearInterval(checkRenderInterval);
          sendResponse({ success: false, error: "CHALLENGE_DETECTED", message: "LinkedIn verification challenge detected." });
          return;
        }

        const nameEl = document.querySelector('h1.text-heading-xlarge, h1.inline.t-24, main h1, .pv-top-card--list h1, .pv-text-details__left-panel h1');
        const hasSections = !!document.querySelector('.pv-profile-card, section.artdeco-card, #about, #experience');

        if (nameEl || hasSections || attempts >= maxRetries) {
          clearInterval(checkRenderInterval);
          const pageCheck = inspectProfilePage();
          sendResponse({
            success: !!nameEl || hasSections,
            rendered: !!nameEl || hasSections,
            attempts: attempts,
            pageCheck: pageCheck
          });
        }
      }, intervalMs);

      return true;
    }

    if (request.action === "INSPECT_CURRENT_PAGE") {
      const check = inspectProfilePage();
      sendResponse({ success: true, ...check });
      return true;
    }

    if (request.action === "EXTRACT_OWN_PROFILE_DOM") {
      const reqId = request.requestId || "unknown";
      const startTime = Date.now();
      console.log(`[LinkedIn Content] DOM extraction requested: ${reqId} (+0ms)`);
      (async () => {
        try {
          // Progressively load sections via viewport scrolling before reading DOM
          await autoScrollAndLoadSections();

          const extractionStart = Date.now();
          console.log(`[LinkedIn Content] Reading DOM structures (+${extractionStart - startTime}ms)`);
          const result = extractProfileFromDom(reqId);
          const totalElapsed = Date.now() - startTime;
          console.log(`[LinkedIn Extraction] DOM_EXTRACTION_COMPLETED: ${reqId} in ${totalElapsed}ms. Success: ${result.success}`);
          sendResponse(result);
        } catch (err) {
          const totalElapsed = Date.now() - startTime;
          console.error(`[LinkedIn Content] DOM extraction failed: ${reqId} after ${totalElapsed}ms`, err);
          sendResponse({
            success: false,
            error: "EXTRACTION_EXCEPTION",
            message: err.message || "Failed to parse profile DOM"
          });
        }
      })();
      return true;
    }

    if (request.action === "EXTRACT_DETAIL_LIST_DOM") {
      const kind = request.kind || "unknown";
      const reqId = request.requestId || "unknown";
      const startTime = Date.now();
      console.log(`[LinkedIn Content] Detail extraction requested for ${kind}: ${reqId}`);
      (async () => {
        try {
          // Scroll to load all items in the detail list
          await autoScrollAndLoadSections();

          const result = extractDetailListPage(kind);
          const totalElapsed = Date.now() - startTime;
          console.log(`[LinkedIn Extraction] DETAIL_EXTRACTION_COMPLETED: ${kind} (${result.count || 0} items) in ${totalElapsed}ms`);
          sendResponse(result);
        } catch (err) {
          console.error(`[LinkedIn Content] Detail extraction failed for ${kind}:`, err);
          sendResponse({
            success: false,
            kind: kind,
            error: "DETAIL_EXTRACTION_EXCEPTION",
            message: err.message,
            items: []
          });
        }
      })();
      return true;
    }

    if (request.action === "WAIT_FOR_SEARCH_RENDER") {
      const maxRetries = request.maxRetries || 15;
      const intervalMs = request.intervalMs || 400;
      console.log(`[LinkedIn Content] WAIT_FOR_SEARCH_RENDER requested (max: ${maxRetries * intervalMs}ms)`);
      (async () => {
        try {
          const renderResult = await waitForSearchResultsRender(maxRetries, intervalMs);
          sendResponse({
            success: renderResult.status === "RESULTS_READY",
            ...renderResult
          });
        } catch (e) {
          sendResponse({ success: false, status: "WAIT_EXCEPTION", error: e.message });
        }
      })();
      return true;
    }

    if (request.action === "EXTRACT_SEARCH_RESULTS_DOM") {
      const reqId = request.requestId || "unknown";
      const queryContext = request.queryContext || {};
      const startTime = Date.now();
      console.log(`[LinkedIn Content] Search results extraction requested (${reqId})`);

      (async () => {
        try {
          // Bounded condition-based wait for dynamic search result containers
          const renderState = await waitForSearchResultsRender(15, 400);
          console.log(`[LinkedIn Content] SEARCH_RENDER_CHECK: status=${renderState.status}, attempts=${renderState.attempts}`);

          // Scroll slightly to allow viewport-bound lazy cards to complete rendering
          window.scrollBy({ top: 400, behavior: 'smooth' });
          await new Promise(r => setTimeout(r, 500));

          const result = extractSearchResultsDom(queryContext);
          result.renderState = renderState;
          const elapsed = Date.now() - startTime;
          console.log(`[LinkedIn Extraction] SEARCH_EXTRACTION_COMPLETED: status=${result.status}, count=${result.count} in ${elapsed}ms`);
          sendResponse(result);
        } catch (err) {
          console.error(`[LinkedIn Content] Error during search results extraction:`, err);
          sendResponse({
            success: false,
            status: "SEARCH_EXTRACTION_EXCEPTION",
            error: "SEARCH_EXTRACTION_EXCEPTION",
            message: err.message,
            results: [],
            count: 0
          });
        }
      })();
      return true;
    }
  };

  chrome.runtime.onMessage.addListener(window.__famewebLinkedInMessageListener);
})();
