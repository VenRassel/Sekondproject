from django.contrib.auth.models import User
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from .models import AuditLog, PCBuild, PCBuildItem, Product


class RBACTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(username='staff1', password='pass12345')
        self.admin_user = User.objects.create_user(username='admin1', password='pass12345')
        self.admin_user.profile.role = 'admin'
        self.admin_user.profile.save(update_fields=['role'])

    def test_signup_forces_staff_role(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'newuser',
                'email': 'new@example.com',
                'password1': 'VeryStrongPass123',
                'password2': 'VeryStrongPass123',
                'role': 'admin',
            },
        )

        self.assertRedirects(response, reverse('landing'))
        created_user = User.objects.get(username='newuser')
        self.assertEqual(created_user.profile.role, 'staff')

    def test_signup_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            username='existing_user',
            email='taken@example.com',
            password='pass12345',
        )

        response = self.client.post(
            reverse('signup'),
            {
                'username': 'newuser2',
                'email': 'TAKEN@example.com',
                'password1': 'VeryStrongPass123',
                'password2': 'VeryStrongPass123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This email is already in use.")
        self.assertFalse(User.objects.filter(username='newuser2').exists())

    def test_staff_cannot_access_product_management(self):
        self.client.login(username='staff1', password='pass12345')

        response = self.client.get(reverse('product'))

        self.assertRedirects(response, reverse('landing'))

    def test_staff_cannot_archive_build(self):
        build = PCBuild.objects.create(user=self.staff_user, total_price='1000.00', status='checked_out')
        self.client.login(username='staff1', password='pass12345')

        response = self.client.post(reverse('archive-build', args=[build.id]), {'next_view': 'active'})

        self.assertRedirects(response, reverse('landing'))
        build.refresh_from_db()
        self.assertFalse(build.is_archived)

    def test_admin_can_delete_archived_build_with_confirmation(self):
        build = PCBuild.objects.create(
            user=self.staff_user,
            total_price='1200.00',
            status='checked_out',
            is_archived=True,
        )
        self.client.login(username='admin1', password='pass12345')

        response = self.client.post(
            reverse('delete-build', args=[build.id]),
            {'next_view': 'archived', 'confirm_delete': 'DELETE'},
        )

        self.assertRedirects(response, f"{reverse('checkout-history')}?view=archived")
        self.assertFalse(PCBuild.objects.filter(id=build.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                action='delete_build',
                status='success',
                user=self.admin_user,
                identifier=str(build.id),
            ).exists()
        )

    def test_admin_delete_archived_build_requires_delete_keyword(self):
        build = PCBuild.objects.create(
            user=self.staff_user,
            total_price='1200.00',
            status='checked_out',
            is_archived=True,
        )
        self.client.login(username='admin1', password='pass12345')

        response = self.client.post(
            reverse('delete-build', args=[build.id]),
            {'next_view': 'archived', 'confirm_delete': 'WRONG'},
        )

        self.assertRedirects(response, f"{reverse('checkout-history')}?view=archived")
        self.assertTrue(PCBuild.objects.filter(id=build.id).exists())

    def test_staff_cannot_delete_archived_build(self):
        build = PCBuild.objects.create(
            user=self.staff_user,
            total_price='1200.00',
            status='checked_out',
            is_archived=True,
        )
        self.client.login(username='staff1', password='pass12345')

        response = self.client.post(
            reverse('delete-build', args=[build.id]),
            {'next_view': 'archived', 'confirm_delete': 'DELETE'},
        )

        self.assertRedirects(response, reverse('landing'))
        self.assertTrue(PCBuild.objects.filter(id=build.id).exists())

    def test_admin_can_bulk_archive_active_builds(self):
        build1 = PCBuild.objects.create(user=self.staff_user, total_price='100.00', status='checked_out', is_archived=False)
        build2 = PCBuild.objects.create(user=self.staff_user, total_price='200.00', status='checked_out', is_archived=False)
        self.client.login(username='admin1', password='pass12345')

        response = self.client.post(
            reverse('bulk-manage-builds'),
            {
                'bulk_action': 'archive',
                'next_view': 'active',
                'selected_build_ids': [str(build1.id), str(build2.id)],
            },
        )

        self.assertRedirects(response, f"{reverse('checkout-history')}?view=active")
        build1.refresh_from_db()
        build2.refresh_from_db()
        self.assertTrue(build1.is_archived)
        self.assertTrue(build2.is_archived)

    def test_admin_bulk_delete_requires_confirmation_keyword(self):
        build = PCBuild.objects.create(
            user=self.staff_user,
            total_price='300.00',
            status='checked_out',
            is_archived=True,
        )
        self.client.login(username='admin1', password='pass12345')

        response = self.client.post(
            reverse('bulk-manage-builds'),
            {
                'bulk_action': 'delete',
                'next_view': 'archived',
                'selected_build_ids': [str(build.id)],
                'confirm_delete': 'WRONG',
            },
        )

        self.assertRedirects(response, f"{reverse('checkout-history')}?view=archived")
        self.assertTrue(PCBuild.objects.filter(id=build.id).exists())

    def test_admin_delete_protected_product_is_handled(self):
        product = Product.objects.create(
            name='Protected CPU',
            description='Used in a checkout',
            price='9999.99',
            quantity=2,
            category='cpu',
        )
        build = PCBuild.objects.create(user=self.staff_user, total_price='9999.99', status='checked_out')
        PCBuildItem.objects.create(build=build, product=product, quantity=1, price_at_time='9999.99')

        self.client.login(username='admin1', password='pass12345')
        response = self.client.post(reverse('delete-product', args=[product.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Product.objects.filter(id=product.id).exists())
        self.assertContains(response, "Cannot delete")

    def test_admin_can_archive_and_restore_product(self):
        product = Product.objects.create(
            name='Archive Me',
            description='toggle state',
            price='100.00',
            quantity=5,
            category='ram',
        )
        self.client.login(username='admin1', password='pass12345')

        archive_response = self.client.post(reverse('archive-product', args=[product.id]))
        self.assertRedirects(archive_response, reverse('product'))
        product.refresh_from_db()
        self.assertTrue(product.is_archived)

        restore_response = self.client.post(reverse('restore-product', args=[product.id]))
        self.assertRedirects(restore_response, reverse('product'))
        product.refresh_from_db()
        self.assertFalse(product.is_archived)

    def test_admin_can_bulk_archive_products(self):
        p1 = Product.objects.create(name='Bulk A', description='', price='100.00', quantity=1, category='ram')
        p2 = Product.objects.create(name='Bulk B', description='', price='200.00', quantity=2, category='cpu')
        self.client.login(username='admin1', password='pass12345')

        response = self.client.post(
            reverse('bulk-manage-products'),
            {
                'bulk_action': 'archive',
                'selected_product_ids': [str(p1.id), str(p2.id)],
                'next_querystring': '',
            },
        )

        self.assertRedirects(response, '/product/')
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(p1.is_archived)
        self.assertTrue(p2.is_archived)

    def test_admin_bulk_delete_products_requires_delete_keyword(self):
        p1 = Product.objects.create(name='Delete Me 1', description='', price='100.00', quantity=1, category='ram')
        p2 = Product.objects.create(name='Delete Me 2', description='', price='200.00', quantity=2, category='cpu')
        self.client.login(username='admin1', password='pass12345')

        response = self.client.post(
            reverse('bulk-manage-products'),
            {
                'bulk_action': 'delete',
                'selected_product_ids': [str(p1.id), str(p2.id)],
                'confirm_delete': 'WRONG',
                'next_querystring': '',
            },
        )

        self.assertRedirects(response, '/product/')
        self.assertTrue(Product.objects.filter(id=p1.id).exists())
        self.assertTrue(Product.objects.filter(id=p2.id).exists())

    def test_archived_products_not_shown_in_pc_builder(self):
        Product.objects.create(
            name='Hidden RAM',
            description='archived',
            price='200.00',
            quantity=10,
            category='ram',
            is_archived=True,
        )
        Product.objects.create(
            name='Visible RAM',
            description='active',
            price='250.00',
            quantity=10,
            category='ram',
            is_archived=False,
        )
        self.client.login(username='staff1', password='pass12345')

        response = self.client.get(reverse('pc-builder'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visible RAM')
        self.assertNotContains(response, 'Hidden RAM')

    def test_user_can_update_own_username_in_profile_settings(self):
        self.client.login(username='staff1', password='pass12345')

        response = self.client.post(
            reverse('profile-settings'),
            {
                'username': 'staff1_renamed',
                'email': '',
                'first_name': '',
                'last_name': '',
            },
        )

        self.assertRedirects(response, reverse('profile-settings'))
        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.username, 'staff1_renamed')

    def test_profile_settings_rejects_duplicate_username(self):
        self.client.login(username='staff1', password='pass12345')

        response = self.client.post(
            reverse('profile-settings'),
            {
                'username': 'admin1',
                'email': '',
                'first_name': '',
                'last_name': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.username, 'staff1')
        self.assertContains(response, "This username is already taken.")


@override_settings(
    LOGIN_RATE_LIMIT_ATTEMPTS=2,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS=60,
    FORGOT_PASSWORD_RATE_LIMIT_ATTEMPTS=1,
    FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS=60,
)
class AuthSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='secureuser',
            email='secure@example.com',
            password='StrongPass123!',
        )

    def test_login_rate_limit_blocks_after_threshold(self):
        login_url = reverse('login')
        payload = {'username': 'secureuser', 'password': 'wrong-pass'}

        response1 = self.client.post(login_url, payload)
        self.assertEqual(response1.status_code, 200)

        response2 = self.client.post(login_url, payload)
        self.assertEqual(response2.status_code, 200)

        response3 = self.client.post(
            login_url,
            {'username': 'secureuser', 'password': 'StrongPass123!'},
            follow=True,
        )
        self.assertEqual(response3.status_code, 200)
        self.assertFalse(response3.wsgi_request.user.is_authenticated)

        self.assertTrue(
            AuditLog.objects.filter(action='login', status='rate_limited', identifier='secureuser').exists()
        )

    def test_forgot_password_rate_limit_blocks_second_attempt(self):
        forgot_url = reverse('forgot_password')

        first_response = self.client.post(forgot_url, {'email': 'secure@example.com'})
        self.assertRedirects(first_response, reverse('forgot_password_done'))

        second_response = self.client.post(forgot_url, {'email': 'secure@example.com'})
        self.assertRedirects(second_response, reverse('forgot_password'))

        self.assertTrue(
            AuditLog.objects.filter(
                action='forgot_password',
                status='rate_limited',
                identifier='secure@example.com',
            ).exists()
        )

    def test_audit_log_created_for_successful_login(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'secureuser', 'password': 'StrongPass123!'},
        )
        self.assertRedirects(response, reverse('landing'))
        self.assertTrue(
            AuditLog.objects.filter(
                action='login',
                status='success',
                user=self.user,
                identifier='secureuser',
            ).exists()
        )
