from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import PCBuild, PCBuildItem, Product


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
