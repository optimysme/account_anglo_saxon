# -*- coding: utf-8 -*-
{
    "name": "Anglo Saxon Accounting ",
    "version": "1.0",
    "depends": [
        "account",
        "stock_account",
        "purchase",
        "product",
        "purchase_stock",
    ],
    "author": "Optimysme Ltd",
    "website": "http://www.optimysme.co.nz",
    "category": "Accounting",
    "description": ("Provides additional functionality and fixes "
                    "for anglo-saxon accounting"),
    "data": [
        "views/company_view.xml",
        "views/account_anglo_saxon.xml",
        "security/account_anglo_saxon.xml",
        "wizards/dispatched_not_invoiced_reconcile.xml"

    ],
    "installable": True,
    "active": False,
}
