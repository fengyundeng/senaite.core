# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.CORE.
#
# SENAITE.CORE is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2018-2024 by it's authors.
# Some rights reserved, see README and LICENSE.

from bika.lims import api
from bika.lims import logger
from bika.lims import senaiteMessageFactory as _
from bika.lims.catalog import SETUP_CATALOG
from senaite.core.permissions import FieldEditResultsInterpretation
from plone import protect
from plone.app.layout.viewlets import ViewletBase
from plone.app.textfield import RichTextValue
from Products.Archetypes.event import ObjectEditedEvent
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope import event


class ResultsInterpretationViewlet(ViewletBase):
    """Viewlet for results interpretation field
    """
    index = ViewPageTemplateFile("templates/resultsinterpretation.pt")

    title = _("Results interpretation")
    icon_name = "resultsinterpretation"

    def available(self):
        return True

    def update(self):
        if self.request.form.get("submitted", False):
            return self.handle_form_submit()
        return self.index()

    def get_panels(self):
        """Returns the objects for which an specific free text area has to be
        rendered for the introduction of results interpretations
        """
        return self.context.getDepartments()

    def handle_form_submit(self):
        """Handle form submission
        """
        protect.CheckAuthenticator(self.request)
        logger.info("Handle ResultsInterpration Submit")
        # Save the results interpretation
        res = self.request.form.get("ResultsInterpretationDepts", [])
        self.context.setResultsInterpretationDepts(res)
        self.add_status_message(_("Changes Saved"), level="info")
        # reindex the object after save to update all catalog metadata
        self.context.reindexObject()
        # notify object edited event
        event.notify(ObjectEditedEvent(self.context))
        return self.request.response.redirect(api.get_url(self.context))

    def add_status_message(self, message, level="info"):
        """Set a portal status message
        """
        return self.context.plone_utils.addPortalMessage(message, level)

    def is_edit_allowed(self):
        """Check if edit is allowed
        """
        checkPermission = self.context.portal_membership.checkPermission
        return checkPermission(FieldEditResultsInterpretation, self.context)

    def get_text(self, department, mode="raw"):
        """Returns the text saved for the selected department
        """
        row = self.context.getResultsInterpretationByDepartment(department)
        rt = RichTextValue(row.get("richtext", ""), "text/plain", "text/html")
        if mode == "output":
            return rt.output
        return rt.raw

    def get_interpretation_templates(self):
        """Return a list of datainfo dicts representing interpretation templates
        """
        sample_type_uid = self.context.getRawSampleType()
        template_uid = self.context.getRawTemplate()

        def is_suitable(obj):
            """Returns whether the interpretation passed-in suits well with
            the underlying sample object
            """
            obj = api.get_object(obj)
            sample_types = obj.getRawSampleTypes() or [sample_type_uid]
            if sample_type_uid in sample_types:
                return True

            analysis_templates = obj.getRawAnalysisTemplates()
            if template_uid in analysis_templates:
                return True

            return False

        def get_data_info(item):
            return {
                "uid": api.get_uid(item),
                "title": api.get_title(item)
            }

        # Get all available templates
        query = {"portal_type": "InterpretationTemplate",
                 "review_state": "active",
                 "sort_on": "sortable_title",
                 "sort_order": "ascending"}
        brains = api.search(query, SETUP_CATALOG)

        # Purge the templates that do not suit well with current sample
        brains = filter(is_suitable, brains)
        return map(get_data_info, brains)
