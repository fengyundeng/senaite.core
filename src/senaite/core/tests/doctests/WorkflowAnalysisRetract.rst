Analysis retract guard and event
--------------------------------

Running this test from the buildout directory:

    bin/test test_textual_doctests -t WorkflowAnalysisRetract


Test Setup
..........

Needed Imports:

    >>> from AccessControl.PermissionRole import rolesForPermissionOn
    >>> from bika.lims import api
    >>> from bika.lims.interfaces import IRetracted
    >>> from bika.lims.utils.analysisrequest import create_analysisrequest
    >>> from bika.lims.workflow import doActionFor as do_action_for
    >>> from bika.lims.workflow import isTransitionAllowed
    >>> from DateTime import DateTime
    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from plone.app.testing import TEST_USER_PASSWORD

Functional Helpers:

    >>> def start_server():
    ...     from Testing.ZopeTestCase.utils import startZServer
    ...     ip, port = startZServer()
    ...     return "http://{}:{}/{}".format(ip, port, portal.id)

    >>> def timestamp(format="%Y-%m-%d"):
    ...     return DateTime().strftime(format)

    >>> def start_server():
    ...     from Testing.ZopeTestCase.utils import startZServer
    ...     ip, port = startZServer()
    ...     return "http://{}:{}/{}".format(ip, port, portal.id)

    >>> def new_ar(services):
    ...     values = {
    ...         'Client': client.UID(),
    ...         'Contact': contact.UID(),
    ...         'DateSampled': date_now,
    ...         'SampleType': sampletype.UID()}
    ...     service_uids = map(api.get_uid, services)
    ...     ar = create_analysisrequest(client, request, values, service_uids)
    ...     transitioned = do_action_for(ar, "receive")
    ...     return ar

    >>> def try_transition(object, transition_id, target_state_id):
    ...      success = do_action_for(object, transition_id)[0]
    ...      state = api.get_workflow_status_of(object)
    ...      return success and state == target_state_id

    >>> def submit_analyses(ar):
    ...     for analysis in ar.getAnalyses(full_objects=True):
    ...         analysis.setResult(13)
    ...         do_action_for(analysis, "submit")

    >>> def get_roles_for_permission(permission, context):
    ...     allowed = set(rolesForPermissionOn(permission, context))
    ...     return sorted(allowed)


Variables:

    >>> portal = self.portal
    >>> request = self.request
    >>> setup = portal.setup
    >>> bikasetup = portal.bika_setup
    >>> date_now = DateTime().strftime("%Y-%m-%d")
    >>> date_future = (DateTime() + 5).strftime("%Y-%m-%d")

We need to create some basic objects for the test:

    >>> setRoles(portal, TEST_USER_ID, ['LabManager',])
    >>> client = api.create(portal.clients, "Client", Name="Happy Hills", ClientID="HH", MemberDiscountApplies=True)
    >>> contact = api.create(client, "Contact", Firstname="Rita", Lastname="Mohale")
    >>> sampletype = api.create(bikasetup.bika_sampletypes, "SampleType", title="Water", Prefix="W")
    >>> labcontact = api.create(bikasetup.bika_labcontacts, "LabContact", Firstname="Lab", Lastname="Manager")
    >>> department = api.create(setup.departments, "Department", title="Chemistry", Manager=labcontact)
    >>> category = api.create(setup.analysiscategories, "AnalysisCategory", title="Metals", Department=department)
    >>> Cu = api.create(bikasetup.bika_analysisservices, "AnalysisService", title="Copper", Keyword="Cu", Price="15", Category=category.UID(), Accredited=True)
    >>> Fe = api.create(bikasetup.bika_analysisservices, "AnalysisService", title="Iron", Keyword="Fe", Price="10", Category=category.UID())
    >>> Au = api.create(bikasetup.bika_analysisservices, "AnalysisService", title="Gold", Keyword="Au", Price="20", Category=category.UID())


Retract transition and guard basic constraints
..............................................

Create an Analysis Request and submit results:

    >>> ar = new_ar([Cu, Fe, Au])
    >>> submit_analyses(ar)

The status of the Analysis Request and its analyses is `to_be_verified`:

    >>> api.get_workflow_status_of(ar)
    'to_be_verified'

    >>> analyses = ar.getAnalyses(full_objects=True)
    >>> map(api.get_workflow_status_of, analyses)
    ['to_be_verified', 'to_be_verified', 'to_be_verified']

Retract one of the analyses:

    >>> analysis = analyses[0]
    >>> try_transition(analysis, "retract", "retracted")
    True
    >>> api.get_workflow_status_of(analysis)
    'retracted'

And one new additional analysis has been added in `unassigned` state:

    >>> analyses = ar.getAnalyses(full_objects=True)
    >>> sorted(map(api.get_workflow_status_of, analyses))
    ['retracted', 'to_be_verified', 'to_be_verified', 'unassigned']

And the Analysis Request has been transitioned to `sample_received`:

    >>> api.get_workflow_status_of(ar)
    'sample_received'

The new analysis is a copy of retracted one:

    >>> retest = filter(lambda an: api.get_workflow_status_of(an) == "unassigned", analyses)[0]
    >>> analysis.getRetest() == retest
    True
    >>> retest.getRetestOf() == analysis
    True
    >>> retest.getKeyword() == analysis.getKeyword()
    True

But it does not keep the result:

    >>> not retest.getResult()
    True

And Result capture date is None:

    >>> not retest.getResultCaptureDate()
    True

If I submit the result for the new analysis:

    >>> retest.setResult(analysis.getResult())
    >>> try_transition(retest, "submit", "to_be_verified")
    True

The status of both the analysis and the Analysis Request is "to_be_verified":

    >>> api.get_workflow_status_of(retest)
    'to_be_verified'
    >>> api.get_workflow_status_of(ar)
    'to_be_verified'

And I can even retract the retest:

    >>> try_transition(retest, "retract", "retracted")
    True
    >>> api.get_workflow_status_of(retest)
    'retracted'

And one new additional analysis has been added in `unassigned` state:

    >>> analyses = ar.getAnalyses(full_objects=True)
    >>> sorted(map(api.get_workflow_status_of, analyses))
    ['retracted', 'retracted', 'to_be_verified', 'to_be_verified', 'unassigned']

And again, the Analysis Request has been transitioned to `sample_received`:

    >>> api.get_workflow_status_of(ar)
    'sample_received'

Auto-rollback of Worksheet on analysis retraction
.................................................

When retracting an analysis from a Worksheet that is in "to_be_verified" state
causes the rollback of the worksheet to "open" state.

Create an Analysis Request and submit results:

    >>> ar = new_ar([Cu, Fe, Au])

Create a new Worksheet, assign all analyses and submit:

    >>> ws = api.create(portal.worksheets, "Worksheet")
    >>> for analysis in ar.getAnalyses(full_objects=True):
    ...     ws.addAnalysis(analysis)
    >>> submit_analyses(ar)

The state for both the Analysis Request and Worksheet is "to_be_verified":

    >>> api.get_workflow_status_of(ar)
    'to_be_verified'
    >>> api.get_workflow_status_of(ws)
    'to_be_verified'

Retract one analysis:

    >>> analysis = ws.getAnalyses()[0]
    >>> try_transition(analysis, "retract", "retracted")
    True

A rollback of the state of Analysis Request and Worksheet takes place:

    >>> api.get_workflow_status_of(ar)
    'sample_received'
    >>> api.get_workflow_status_of(ws)
    'open'

And both contain an additional analysis:

    >>> len(ar.getAnalyses())
    4
    >>> len(ws.getAnalyses())
    4

The state of this additional analysis, the retest, is "assigned":

    >>> analyses = ar.getAnalyses(full_objects=True)
    >>> retest = filter(lambda an: api.get_workflow_status_of(an) == "assigned", analyses)[0]
    >>> retest.getKeyword() == analysis.getKeyword()
    True
    >>> retest in ws.getAnalyses()
    True


Retraction of results for analyses with dependents
..................................................

When retracting an analysis other analyses depends on (dependents), then the
retraction of a dependency causes the auto-retraction of its dependents.
Dependencies are retracted too.

Prepare a calculation that depends on `Cu` and assign it to `Fe` analysis:

    >>> calc_fe = api.create(bikasetup.bika_calculations, 'Calculation', title='Calc for Fe')
    >>> calc_fe.setFormula("[Cu]*10")
    >>> Fe.setCalculation(calc_fe)

Prepare a calculation that depends on `Fe` and assign it to `Au` analysis:

    >>> calc_au = api.create(bikasetup.bika_calculations, 'Calculation', title='Calc for Au')
    >>> calc_au.setFormula("([Fe])/2")
    >>> Au.setCalculation(calc_au)

Create an Analysis Request:

    >>> ar = new_ar([Cu, Fe, Au])
    >>> analyses = ar.getAnalyses(full_objects=True)
    >>> cu_analysis = filter(lambda an: an.getKeyword()=="Cu", analyses)[0]
    >>> fe_analysis = filter(lambda an: an.getKeyword()=="Fe", analyses)[0]
    >>> au_analysis = filter(lambda an: an.getKeyword()=="Au", analyses)[0]

TODO This should not be like this, but the calculation is performed by
`ajaxCalculateAnalysisEntry`. The calculation logic must be moved to
'api.analysis.calculate`:

    >>> cu_analysis.setResult(20)
    >>> fe_analysis.setResult(12)
    >>> au_analysis.setResult(10)

Submit `Au` analysis and the rest will follow:

    >>> try_transition(au_analysis, "submit", "to_be_verified")
    True
    >>> api.get_workflow_status_of(au_analysis)
    'to_be_verified'
    >>> api.get_workflow_status_of(fe_analysis)
    'to_be_verified'
    >>> api.get_workflow_status_of(cu_analysis)
    'to_be_verified'
    >>> api.get_workflow_status_of(ar)
    'to_be_verified'

If I retract `Fe`, `Au` analysis is retracted automatically too:

    >>> try_transition(fe_analysis, "retract", "retracted")
    True
    >>> api.get_workflow_status_of(fe_analysis)
    'retracted'
    >>> api.get_workflow_status_of(au_analysis)
    'retracted'

As well as `Cu` analysis (a dependency of `Fe`):

    >>> api.get_workflow_status_of(cu_analysis)
    'retracted'

Hence, three new analyses are generated in accordance:

    >>> analyses = ar.getAnalyses(full_objects=True)
    >>> len(analyses)
    6
    >>> au_analyses = filter(lambda an: an.getKeyword()=="Au", analyses)
    >>> sorted(map(api.get_workflow_status_of, au_analyses))
    ['retracted', 'unassigned']
    >>> fe_analyses = filter(lambda an: an.getKeyword()=="Fe", analyses)
    >>> sorted(map(api.get_workflow_status_of, fe_analyses))
    ['retracted', 'unassigned']
    >>> cu_analyses = filter(lambda an: an.getKeyword()=="Cu", analyses)
    >>> sorted(map(api.get_workflow_status_of, cu_analyses))
    ['retracted', 'unassigned']

And the current state of the Analysis Request is `sample_received` now:

    >>> api.get_workflow_status_of(ar)
    'sample_received'


IRetracted interface is provided by retracted analyses
......................................................

When retracted, routine analyses are marked with the `IRetracted` interface:

    >>> sample = new_ar([Cu])
    >>> submit_analyses(sample)
    >>> analysis = sample.getAnalyses(full_objects=True)[0]
    >>> IRetracted.providedBy(analysis)
    False

    >>> success = do_action_for(analysis, "retract")
    >>> IRetracted.providedBy(analysis)
    True

But the retest does not provide `IRetracted`:

    >>> retest = analysis.getRetest()
    >>> IRetracted.providedBy(retest)
    False


Retract an analysis with a result that is a Detection Limit
...........................................................

Allow the user to manually enter the detection limit as the result:

    >>> Cu.setAllowManualDetectionLimit(True)

Create the sample:

    >>> sample = new_ar([Cu])
    >>> cu = sample.getAnalyses(full_objects=True)[0]
    >>> cu.setResult("< 10")
    >>> success = do_action_for(cu, "submit")
    >>> cu.getResult()
    '10'

    >>> cu.getFormattedResult(html=False)
    '< 10'

    >>> cu.isLowerDetectionLimit()
    True

    >>> cu.getDetectionLimitOperand()
    '<'

The Detection Limit is not kept on the retest:

    >>> success = do_action_for(analysis, "retract")
    >>> retest = analysis.getRetest()
    >>> retest.getResult()
    ''

    >>> retest.getFormattedResult(html=False)
    ''

    >>> retest.isLowerDetectionLimit()
    False

    >>> retest.getDetectionLimitOperand()
    ''

Do the same with Upper Detection Limit (UDL):

    >>> sample = new_ar([Cu])
    >>> cu = sample.getAnalyses(full_objects=True)[0]
    >>> cu.setResult("> 10")
    >>> success = do_action_for(cu, "submit")
    >>> cu.getResult()
    '10'

    >>> cu.getFormattedResult(html=False)
    '> 10'

    >>> cu.isUpperDetectionLimit()
    True

    >>> cu.getDetectionLimitOperand()
    '>'

The Detection Limit is not kept on the retest:

    >>> success = do_action_for(analysis, "retract")
    >>> retest = analysis.getRetest()
    >>> retest.getResult()
    ''

    >>> retest.getFormattedResult(html=False)
    ''

    >>> retest.isUpperDetectionLimit()
    False

    >>> retest.getDetectionLimitOperand()
    ''
