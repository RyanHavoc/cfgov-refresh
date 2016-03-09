'use strict';

// Required modules.
var dataHook = require( '../modules/util/data-hook' );
var EventObserver = require( '../modules/util/EventObserver' );
var standardType = require( '../modules/util/standard-type' );

/**
 * FlyoutMenu
 * @class
 *
 * @classdesc Initializes new FlyoutMenu behavior.
 * As added JS behavior, this is added through HTML data-js-hook attributes.
 *
 * Structure is:
 * flyout-menu
 *   flyout-menu_trigger
 *   flyout-menu_content
 *     flyout-menu_alt-trigger
 *
 * The alt-trigger is for a back button, which may obscure the first trigger.
 * The flyout can be triggered three ways: through a click of the trigger or
 * through the click of an alt-trigger.
 *
 * @param {HTMLNode} element - The DOM element to attach FlyoutMenu behavior.
 * @returns {FlyoutMenu} An instance.
 */
function FlyoutMenu( element ) { // eslint-disable-line max-statements, no-inline-comments, max-len

  var BASE_CLASS = 'flyout-menu';
  var SEL_PREFIX = '[' + standardType.JS_HOOK + '=' + BASE_CLASS;

  var BASE_SEL = SEL_PREFIX + ']';
  var ALT_TRIGGER_SEL = SEL_PREFIX + '_alt-trigger]';
  var CONTENT_SEL = SEL_PREFIX + '_content]';
  var TRIGGER_SEL = SEL_PREFIX + '_trigger]';

  // TODO: Update atomic-helpers to support CSS selectors for validity check.
  var _dom = dataHook.contains( element, BASE_CLASS ) ? element : null;
  if ( !_dom ) _dom = element.parentNode.querySelector( BASE_SEL );
  if ( !_dom ) { throw new Error( 'Selector not found on passed node!' ); }

  var _triggerDom = _dom.querySelector( TRIGGER_SEL );
  var _contentDom = _dom.querySelector( CONTENT_SEL );

  if ( !_triggerDom ) { throw new Error( TRIGGER_SEL + ' is missing!' ); }
  if ( !_contentDom ) { throw new Error( CONTENT_SEL + ' is missing!' ); }

  var _altTriggerDom = _dom.querySelector( ALT_TRIGGER_SEL );

  var _isExpanded = false;
  var _isAnimating = false;

  var _expandTransition;
  var _collapseTransition;
  var _expandTransitionMethod;
  var _collapseTransitionMethod;

  // Needed to add and remove events to transitions.
  var _expandEndBinded = _expandEnd.bind( this );
  var _collapseEndBinded = _collapseEnd.bind( this );

  // Set this function to a queued collapse function,
  // which is called if collapse is called while
  // expand is animating.
  var _deferFunct = standardType.noopFunct;
  var _collapseBinded = collapse.bind( this );

  /**
   * @returns {FlyoutMenu} An instance.
   */
  function init() {
    var triggerClickedBinded = _triggerClicked.bind( this );
    _triggerDom.addEventListener( 'click', triggerClickedBinded );

    if ( _altTriggerDom ) {
      // If menu contains a submenu but doesn't have
      // its own alternative trigger (such as a Back button),
      // then the altTriggerDom may be in the submenu and we
      // need to remove the reference.
      var subMenu = _dom.querySelector( BASE_SEL );
      if ( subMenu && subMenu.contains( _altTriggerDom ) ) {
        _altTriggerDom = null;
      } else {
        _altTriggerDom.addEventListener( 'click', triggerClickedBinded );
      }
    }

    return this;
  }

  /**
   * Event handler for when the search input trigger is clicked,
   * which opens/closes the search input.
   * @param {MouseEvent} event - The flyout trigger was clicked.
   */
  function _triggerClicked( event ) {
    event.preventDefault();
    this.dispatchEvent( 'triggerClick', { target: this } );
    if ( _isExpanded ) {
      this.collapse();
    } else {
      this.expand();
    }
  }

  /**
   * Open the search box.
   * @returns {FlyoutMenu} An instance.
   */
  function expand() {
    if ( !_isExpanded && !_isAnimating ) {
      _deferFunct = standardType.noopFunct;
      this.dispatchEvent( 'expandBegin', { target: this } );
      _isExpanded = true;
      _isAnimating = true;
      if ( _expandTransitionMethod ) {
        // The following method is defined in the transition, not this file.
        _expandTransitionMethod();
        if ( _expandTransition && _collapseTransition.isAnimated() ) {
          _expandTransition
            .addEventListener( 'transitionEnd', _expandEndBinded );
        } else {
          _expandEndBinded();
        }
      } else {
        _expandEndBinded();
      }
    }

    return this;
  }

  /**
   * Close the search box.
   * If collapse is called when expand animation is underway,
   * save a deferred call to collapse, which is called when
   * expand completes.
   * @returns {FlyoutMenu} An instance.
   */
  function collapse() {
    if ( _isExpanded && !_isAnimating ) {
      _deferFunct = standardType.noopFunct;
      this.dispatchEvent( 'collapseBegin', { target: this } );
      _isExpanded = false;
      _isAnimating = true;
      if ( _collapseTransitionMethod ) {
        // The following method is defined in the transition, not this file.
        _collapseTransitionMethod();
        if ( _collapseTransition && _collapseTransition.isAnimated() ) {
          _collapseTransition
            .addEventListener( 'transitionEnd', _collapseEndBinded );
        } else {
          _collapseEndBinded();
        }
      } else {
        _collapseEndBinded();
      }
      _triggerDom.setAttribute( 'aria-expanded', 'false' );
      _contentDom.setAttribute( 'aria-expanded', 'false' );
      _triggerDom.focus();
    } else {
      _deferFunct = _collapseBinded;
    }

    return this;
  }

  /**
   * Expand animation has completed.
   * Call deferred collapse function,
   * if set (otherwise it will call a noop function).
   */
  function _expandEnd() {
    _isAnimating = false;
    if ( _expandTransition ) {
      _expandTransition
        .removeEventListener( 'transitionEnd', _expandEndBinded );
    }
    this.dispatchEvent( 'expandEnd', { target: this } );
    _triggerDom.setAttribute( 'aria-expanded', 'true' );
    _contentDom.setAttribute( 'aria-expanded', 'true' );
    // Call collapse, if it was called while expand was animating.
    _deferFunct();
  }

  /**
   * Collapse animation has completed.
   */
  function _collapseEnd() {
    _isAnimating = false;
    if ( _collapseTransition ) {
      _collapseTransition
        .removeEventListener( 'transitionEnd', _collapseEndBinded );
    }
    this.dispatchEvent( 'collapseEnd', { target: this } );
  }

  /**
   * @param {MoveTransition|AlphaTransition} transition
   *   A transition instance to watch for events on.
   * @param {Function} method
   *   The transition method to call on expand.
   */
  function setExpandTransition( transition, method ) {
    _expandTransition = transition;
    _expandTransitionMethod = method;
  }

  /**
   * @param {MoveTransition|AlphaTransition} transition
   *   A transition instance to watch for events on.
   * @param {Function} method
   *   The transition method to call on collapse.
   */
  function setCollapseTransition( transition, method ) {
    _collapseTransition = transition;
    _collapseTransitionMethod = method;
  }

  /**
   * @param {string} type
   *   (Optional) The type of transition to return.
   *   Accepts 'expand' or 'collapse'.
   *   `FlyoutMenu.EXPAND_TYPE` and `FlyoutMenu.COLLAPSE_TYPE` can be used
   *   as type-safe constants passed into this method.
   *   If neither or something else is supplied, expand type is returned.
   * @returns {MoveTransition|AlphaTransition}
   *   A transition instance set on this instance, or undefined if none is set.
   */
  function getTransition( type ) {
    if ( type === FlyoutMenu.COLLAPSE_TYPE ) {
      return _collapseTransition;
    }

    return _expandTransition;
  }

  /**
   * @returns {Object}
   *   Hash of trigger, alternative trigger, and content DOM references.
   */
  function getDom() {
    return {
      altTrigger: _altTriggerDom,
      content:    _contentDom,
      trigger:    _triggerDom
    };
  }

  // Attach public events.
  var eventObserver = new EventObserver();
  this.addEventListener = eventObserver.addEventListener;
  this.removeEventListener = eventObserver.removeEventListener;
  this.dispatchEvent = eventObserver.dispatchEvent;

  this.init = init;
  this.expand = expand;
  this.collapse = collapse;
  this.setExpandTransition = setExpandTransition;
  this.setCollapseTransition = setCollapseTransition;
  this.getTransition = getTransition;
  this.getDom = getDom;

  // Public static properties.
  FlyoutMenu.EXPAND_TYPE = 'expand';
  FlyoutMenu.COLLAPSE_TYPE = 'collapse';

  return this;
}

module.exports = FlyoutMenu;
