public class Main {
    public static void main(String[] args) {
        Calculator calculator = new Calculator();

        // Test power method
        System.out.println("2^3 = " + calculator.power(2, 3));
        System.out.println("5^0 = " + calculator.power(5, 0));
    }
}